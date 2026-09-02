import os
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


DB = None
DATABASE_URL = None
USE_POSTGRES = False
_sqlite_write_lock = threading.Lock()
_POSTGRES_POOL_MINCONN = 1
_POSTGRES_POOL_MAXCONN = 50
_POSTGRES_POOL_WAIT_SECONDS = 30
_POSTGRES_CONNECT_TIMEOUT_SECONDS = 10


def configure_database(db_path: str, database_url: str | None = None) -> None:
    global DB, DATABASE_URL, USE_POSTGRES
    DB = db_path
    DATABASE_URL = database_url
    USE_POSTGRES = bool(database_url)


def sql(sqlite_sql, postgres_sql=None):
    if USE_POSTGRES:
        return postgres_sql or sqlite_sql.replace("?", "%s")
    return sqlite_sql


def _setting_int(name: str, default: int, minimum: int) -> int:
    value = os.environ.get(name)
    if value is None:
        try:
            value = st.secrets.get(name)
        except Exception:
            value = None
    try:
        parsed = int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


class DBConnection:
    """Connection wrapper for the cached SQLite connection or pooled Postgres."""

    def __init__(self, raw: Any, *, lock=None, pool=None):
        self._raw: Any = raw
        self._lock = lock
        self._pool = pool

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False

    def _replace_postgres_connection(self):
        if self._pool is None:
            return False
        try:
            if self._raw is not None:
                self._pool.putconn(self._raw, close=True)
        except Exception:
            pass
        self._raw = _postgres_pool_getconn(self._pool)
        return True

    def _postgres_connection_closed(self):
        return self._pool is not None and (self._raw is None or getattr(self._raw, "closed", True))

    def _ensure_postgres_connection(self):
        if self._postgres_connection_closed():
            self._replace_postgres_connection()

    def _is_postgres_connection_error(self, error):
        if self._pool is None:
            return False
        import psycopg2
        return isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError))

    def execute(self, query, params=None):
        if self._lock is not None:
            with self._lock:
                return self._raw.execute(query, params or ())
        self._ensure_postgres_connection()
        cursor = None
        try:
            cursor = self._raw.cursor()
            cursor.execute(query, params or ())
            return cursor
        except Exception as error:
            if not self._is_postgres_connection_error(error):
                if cursor is not None:
                    cursor.close()
                raise
            if cursor is not None:
                cursor.close()
            self._replace_postgres_connection()
            cursor = self._raw.cursor()
            cursor.execute(query, params or ())
            return cursor

    def cursor(self):
        if self._lock is not None:
            return self._raw.cursor()
        self._ensure_postgres_connection()
        try:
            return self._raw.cursor()
        except Exception as error:
            if not self._is_postgres_connection_error(error):
                raise
            self._replace_postgres_connection()
            return self._raw.cursor()

    def _read_sql_unlocked(self, query, params=None) -> pd.DataFrame:
        if isinstance(self._raw, sqlite3.Connection):
            return pd.read_sql_query(query, self._raw, params=params)

        self._ensure_postgres_connection()
        cursor = None
        try:
            cursor = self._raw.cursor()
            cursor.execute(query, params or ())
        except Exception as error:
            if not self._is_postgres_connection_error(error):
                if cursor is not None:
                    cursor.close()
                raise
            if cursor is not None:
                cursor.close()
            self._replace_postgres_connection()
            cursor = self._raw.cursor()
            cursor.execute(query, params or ())

        try:
            rows = cursor.fetchall()
            columns = [column[0] for column in cursor.description or []]
            return pd.DataFrame(rows, columns=columns)
        finally:
            cursor.close()

    def read_sql(self, query, params=None) -> pd.DataFrame:
        if self._lock is not None:
            with self._lock:
                return self._read_sql_unlocked(query, params)
        return self._read_sql_unlocked(query, params)

    def commit(self):
        if self._lock is not None:
            with self._lock:
                self._raw.commit()
        else:
            self._ensure_postgres_connection()
            try:
                self._raw.commit()
            except Exception as error:
                if not self._is_postgres_connection_error(error):
                    try:
                        self._raw.rollback()
                    except Exception:
                        self._replace_postgres_connection()
                    raise
                self._replace_postgres_connection()
                raise RuntimeError("Database connection was reset before commit. Please submit again.") from error

    def close(self):
        if self._pool is not None:
            raw = self._raw
            self._raw = None
            if raw is None:
                return
            try:
                if not raw.closed:
                    raw.rollback()
                self._pool.putconn(raw)
            except Exception:
                try:
                    self._pool.putconn(raw, close=True)
                except Exception:
                    pass


@st.cache_resource(show_spinner=False)
def _sqlite_connection():
    assert DB is not None, "configure_database() must be called before any database access"
    return sqlite3.connect(DB, check_same_thread=False)


@st.cache_resource(show_spinner=False)
def _postgres_pool():
    from psycopg2.pool import ThreadedConnectionPool

    minconn = _setting_int("POSTGRES_POOL_MINCONN", _POSTGRES_POOL_MINCONN, 1)
    maxconn = _setting_int("POSTGRES_POOL_MAXCONN", _POSTGRES_POOL_MAXCONN, minconn)
    return ThreadedConnectionPool(
        minconn,
        maxconn,
        DATABASE_URL,
        connect_timeout=_POSTGRES_CONNECT_TIMEOUT_SECONDS,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )


def _postgres_pool_getconn(pool):
    import psycopg2
    from psycopg2.pool import PoolError

    wait_seconds = _setting_int("POSTGRES_POOL_WAIT_SECONDS", _POSTGRES_POOL_WAIT_SECONDS, 0)
    deadline = time.monotonic() + wait_seconds
    delay = 0.05
    while True:
        try:
            return pool.getconn()
        except (PoolError, psycopg2.OperationalError, psycopg2.InterfaceError) as error:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "The database connection pool is busy or temporarily unreachable. "
                    "Please wait a few seconds and try again."
                ) from error
            time.sleep(delay)
            delay = min(delay * 1.5, 0.5)


def conn():
    if USE_POSTGRES:
        pool = _postgres_pool()
        database = DBConnection(_postgres_pool_getconn(pool), pool=pool)
        try:
            database.execute("SELECT 1")
        except Exception:
            database.close()
            raise
        return database
    return DBConnection(_sqlite_connection(), lock=_sqlite_write_lock)


@st.cache_resource(show_spinner=False)
def ensure_schema():
    with conn() as connection:
        connection.execute(sql("""
            CREATE TABLE IF NOT EXISTS participants(
                pid TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                pin TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """))
        connection.execute(sql(
            """
            CREATE TABLE IF NOT EXISTS challenge_attempts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pid TEXT NOT NULL,
                level INTEGER NOT NULL,
                challenge TEXT NOT NULL,
                answer TEXT,
                correct INTEGER NOT NULL,
                points INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS challenge_attempts(
                id SERIAL PRIMARY KEY,
                pid TEXT NOT NULL,
                level INTEGER NOT NULL,
                challenge TEXT NOT NULL,
                answer TEXT,
                correct INTEGER NOT NULL,
                points INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
        ))
        try:
            connection.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_one_correct_per_challenge
                ON challenge_attempts(pid, challenge)
                WHERE correct = 1
            """)
        except Exception:
            pass
        connection.commit()
    return True


def make_pid(first, last, pin):
    return f"{first.strip().lower()}|{last.strip().lower()}|{pin.strip()}"


def find_participant_pid_by_name(first, last):
    with conn() as connection:
        row = connection.execute(
            sql("SELECT pid FROM participants WHERE LOWER(first_name)=? AND LOWER(last_name)=?"),
            (first.strip().lower(), last.strip().lower()),
        ).fetchone()
    return row[0] if row else None


def participant_exists(pid):
    with conn() as connection:
        row = connection.execute(
            sql("SELECT 1 FROM participants WHERE pid=?"),
            (pid,),
        ).fetchone()
    return row is not None


def register_participant(first, last, pin):
    pid = make_pid(first, last, pin)
    with conn() as connection:
        row = connection.execute(
            sql("SELECT first_name, last_name FROM participants WHERE pid=?"),
            (pid,),
        ).fetchone()
        if row:
            return pid, row[0], row[1]
        connection.execute(
            sql("INSERT INTO participants VALUES(?,?,?,?,?)"),
            (pid, first.strip(), last.strip(), pin.strip(), datetime.now().isoformat(timespec="seconds")),
        )
        connection.commit()
    all_participants.clear()
    leaderboard.clear()
    return pid, first.strip(), last.strip()


@st.cache_data(show_spinner=False)
def all_participants() -> pd.DataFrame:
    """Every registered participant with their PIN, for the admin dashboard's
    PIN lookup -- includes participants with zero recorded attempts yet,
    unlike a query joined through challenge_attempts."""
    with conn() as connection:
        return connection.read_sql(
            sql('SELECT pid AS "PID", first_name AS "First name", last_name AS "Last name", '
                'pin AS "PIN", created_at AS "Registered" FROM participants '
                "ORDER BY created_at")
        )


def is_duplicate_correct_attempt(error):
    if isinstance(error, sqlite3.IntegrityError):
        return True
    if USE_POSTGRES:
        import psycopg2
        if isinstance(error, psycopg2.IntegrityError):
            return True
    return False


def add_attempt(pid, level, challenge, answer, correct, points):
    with conn() as connection:
        try:
            connection.execute(
                sql("""INSERT INTO challenge_attempts(pid,level,challenge,answer,correct,points,created_at)
                   VALUES(?,?,?,?,?,?,?)"""),
                (
                    pid,
                    level,
                    challenge,
                    str(answer),
                    1 if correct else 0,
                    int(points),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            connection.commit()
        except Exception as error:
            if correct and is_duplicate_correct_attempt(error):
                return False
            raise
    participant_stats.clear()
    leaderboard.clear()
    return True


def reset_participant_attempts(pid):
    with conn() as connection:
        connection.execute(sql("DELETE FROM challenge_attempts WHERE pid=?"), (pid,))
        connection.commit()
    participant_stats.clear()
    leaderboard.clear()


def delete_participant(pid):
    with conn() as connection:
        connection.execute(sql("DELETE FROM challenge_attempts WHERE pid=?"), (pid,))
        connection.execute(sql("DELETE FROM participants WHERE pid=?"), (pid,))
        connection.commit()
    participant_stats.clear()
    all_participants.clear()
    leaderboard.clear()


@st.cache_data(show_spinner=False)
def participant_stats(pid) -> pd.DataFrame:
    with conn() as connection:
        return connection.read_sql(
            sql("SELECT * FROM challenge_attempts WHERE pid=? ORDER BY id"),
            params=(pid,),
        )


@st.cache_data(show_spinner=False)
def leaderboard() -> pd.DataFrame:
    with conn() as connection:
        df = connection.read_sql("""
            SELECT p.pid AS "PID",
                   p.first_name || ' ' || p.last_name AS "Name",
                   COALESCE(SUM(a.points),0) AS "XP",
                   COALESCE(SUM(a.correct),0) AS "Correct",
                   COUNT(a.id) AS "Attempts"
            FROM participants p
            LEFT JOIN challenge_attempts a ON a.pid=p.pid
            GROUP BY p.pid
            ORDER BY "XP" DESC, "Correct" DESC, "Attempts" ASC
        """)
    if not df.empty:
        df.insert(0, "Rank", range(1, len(df) + 1))
    return df


def level_score(pid, level) -> int:
    df = participant_stats(pid)
    if df.empty:
        return 0
    matching_rows: pd.DataFrame = df.loc[df["level"] == level]
    points = pd.Series(matching_rows["points"])
    return int(points.sum())


def total_xp(pid) -> int:
    df = participant_stats(pid)
    if df.empty:
        return 0
    points = pd.Series(df["points"])
    return int(points.sum())
