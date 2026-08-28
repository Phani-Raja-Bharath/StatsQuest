import sqlite3
import threading
from datetime import datetime

import pandas as pd
import streamlit as st


DB = None
DATABASE_URL = None
USE_POSTGRES = False
_sqlite_write_lock = threading.Lock()


def configure_database(db_path: str, database_url: str | None = None) -> None:
    global DB, DATABASE_URL, USE_POSTGRES
    DB = db_path
    DATABASE_URL = database_url
    USE_POSTGRES = bool(database_url)


def sql(sqlite_sql, postgres_sql=None):
    if USE_POSTGRES:
        return postgres_sql or sqlite_sql.replace("?", "%s")
    return sqlite_sql


class DBConnection:
    """Connection wrapper for the cached SQLite connection or pooled Postgres."""

    def __init__(self, raw, *, lock=None, pool=None):
        self._raw = raw
        self._lock = lock
        self._pool = pool

    def _replace_postgres_connection(self):
        if self._pool is None:
            return False
        try:
            self._pool.putconn(self._raw, close=True)
        except Exception:
            pass
        self._raw = self._pool.getconn()
        return True

    def _is_postgres_connection_error(self, error):
        if self._pool is None:
            return False
        import psycopg2
        return isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError))

    def execute(self, query, params=None):
        if self._lock is not None:
            with self._lock:
                return self._raw.execute(query, params or ())
        try:
            cursor = self._raw.cursor()
            cursor.execute(query, params or ())
            return cursor
        except Exception as error:
            if not self._is_postgres_connection_error(error):
                raise
            self._replace_postgres_connection()
            cursor = self._raw.cursor()
            cursor.execute(query, params or ())
            return cursor

    def cursor(self):
        return self._raw.cursor()

    def _read_sql_unlocked(self, query, params=None) -> pd.DataFrame:
        if isinstance(self._raw, sqlite3.Connection):
            return pd.read_sql_query(query, self._raw, params=params)

        try:
            cursor = self._raw.cursor()
            cursor.execute(query, params or ())
        except Exception as error:
            if not self._is_postgres_connection_error(error):
                raise
            self._replace_postgres_connection()
            cursor = self._raw.cursor()
            cursor.execute(query, params or ())

        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description or []]
        cursor.close()
        return pd.DataFrame(rows, columns=columns)

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
            try:
                self._raw.commit()
            except Exception as error:
                if not self._is_postgres_connection_error(error):
                    raise
                self._replace_postgres_connection()
                raise RuntimeError("Database connection was reset before commit. Please submit again.") from error

    def close(self):
        if self._pool is not None:
            self._pool.putconn(self._raw)


@st.cache_resource(show_spinner=False)
def _sqlite_connection():
    assert DB is not None, "configure_database() must be called before any database access"
    return sqlite3.connect(DB, check_same_thread=False)


@st.cache_resource(show_spinner=False)
def _postgres_pool():
    from psycopg2.pool import ThreadedConnectionPool

    return ThreadedConnectionPool(
        1,
        10,
        DATABASE_URL,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )


def conn():
    if USE_POSTGRES:
        pool = _postgres_pool()
        database = DBConnection(pool.getconn(), pool=pool)
        database.execute("SELECT 1")
        return database
    return DBConnection(_sqlite_connection(), lock=_sqlite_write_lock)


@st.cache_resource(show_spinner=False)
def ensure_schema():
    connection = conn()
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
    connection.close()
    return True


def make_pid(first, last, pin):
    return f"{first.strip().lower()}|{last.strip().lower()}|{pin.strip()}"


def find_participant_pid_by_name(first, last):
    connection = conn()
    row = connection.execute(
        sql("SELECT pid FROM participants WHERE LOWER(first_name)=? AND LOWER(last_name)=?"),
        (first.strip().lower(), last.strip().lower()),
    ).fetchone()
    connection.close()
    return row[0] if row else None


def register_participant(first, last, pin):
    pid = make_pid(first, last, pin)
    connection = conn()
    row = connection.execute(
        sql("SELECT first_name, last_name FROM participants WHERE pid=?"),
        (pid,),
    ).fetchone()
    if row:
        connection.close()
        return pid, row[0], row[1]
    connection.execute(
        sql("INSERT INTO participants VALUES(?,?,?,?,?)"),
        (pid, first.strip(), last.strip(), pin.strip(), datetime.now().isoformat(timespec="seconds")),
    )
    connection.commit()
    connection.close()
    all_participants.clear()
    leaderboard.clear()
    return pid, first.strip(), last.strip()


@st.cache_data(show_spinner=False)
def all_participants() -> pd.DataFrame:
    """Every registered participant with their PIN, for the admin dashboard's
    PIN lookup -- includes participants with zero recorded attempts yet,
    unlike a query joined through challenge_attempts."""
    connection = conn()
    df = connection.read_sql(
        sql('SELECT pid AS "PID", first_name AS "First name", last_name AS "Last name", '
            'pin AS "PIN", created_at AS "Registered" FROM participants '
            "ORDER BY created_at")
    )
    connection.close()
    return df


def is_duplicate_correct_attempt(error):
    if isinstance(error, sqlite3.IntegrityError):
        return True
    if USE_POSTGRES:
        import psycopg2
        if isinstance(error, psycopg2.IntegrityError):
            return True
    return False


def add_attempt(pid, level, challenge, answer, correct, points):
    connection = conn()
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
    finally:
        connection.close()
    participant_stats.clear()
    leaderboard.clear()
    return True


def reset_participant_attempts(pid):
    connection = conn()
    try:
        connection.execute(sql("DELETE FROM challenge_attempts WHERE pid=?"), (pid,))
        connection.commit()
    finally:
        connection.close()
    participant_stats.clear()
    leaderboard.clear()


def delete_participant(pid):
    connection = conn()
    try:
        connection.execute(sql("DELETE FROM challenge_attempts WHERE pid=?"), (pid,))
        connection.execute(sql("DELETE FROM participants WHERE pid=?"), (pid,))
        connection.commit()
    finally:
        connection.close()
    participant_stats.clear()
    all_participants.clear()
    leaderboard.clear()


@st.cache_data(show_spinner=False)
def participant_stats(pid) -> pd.DataFrame:
    connection = conn()
    df = connection.read_sql(
        sql("SELECT * FROM challenge_attempts WHERE pid=? ORDER BY id"),
        params=(pid,),
    )
    connection.close()
    return df


@st.cache_data(show_spinner=False)
def leaderboard() -> pd.DataFrame:
    connection = conn()
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
    connection.close()
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
