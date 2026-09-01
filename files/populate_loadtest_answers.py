import os
import sqlite3
from datetime import datetime

import streamlit as st

import db
from scoring import CHALLENGE_POINTS, LEVEL_CHALLENGES, PERFECT_SCORE


APP_DIR = os.path.dirname(os.path.abspath(__file__))
ASSESSMENT_KEYS = ["CENTER", "SPREAD", "DISTRIBUTION", "ARRIVAL", "SIMULATION"]
POST_ANSWERS = {
    "CENTER": "Mean",
    "SPREAD": "Standard deviation",
    "DISTRIBUTION": "Binomial",
    "ARRIVAL": "Exponential",
    "SIMULATION": "To estimate possible outcomes and their chances",
}


def configured_database_url():
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("NEON_DATABASE_URL")
        or st.secrets.get("DATABASE_URL")
        or st.secrets.get("NEON_DATABASE_URL")
    )


def loadtest_attempts():
    attempts = [(0, "SRL_GOAL", "Finish all StatsQuest levels", True, 0)]

    for key in ASSESSMENT_KEYS:
        attempts.append((0, f"PRE_{key}", "Comfortable", False, 0))

    for level, challenges in LEVEL_CHALLENGES.items():
        for challenge in challenges:
            points = 0 if challenge.endswith("_BONUS") else CHALLENGE_POINTS.get(challenge, 0)
            attempts.append((level, challenge, "Load test correct answer", True, points))

    for key, answer in POST_ANSWERS.items():
        attempts.append((6, f"POST_{key}", answer, True, 0))

    for key in ASSESSMENT_KEYS:
        attempts.append((6, f"POSTSELF_{key}", "Very comfortable", False, 0))

    return attempts


def matching_loadtest_users():
    participants = db.all_participants()
    return participants[
        participants["First name"].str.startswith("LoadTest", na=False)
        & (participants["Last name"] == "User")
    ]


def bulk_insert_postgres(database_url, rows):
    import psycopg2
    from psycopg2.extras import execute_values

    insert_sql = """
        INSERT INTO challenge_attempts(pid, level, challenge, answer, correct, points, created_at)
        SELECT data.pid, data.level, data.challenge, data.answer, data.correct, data.points, data.created_at
        FROM (VALUES %s) AS data(pid, level, challenge, answer, correct, points, created_at)
        WHERE NOT EXISTS (
            SELECT 1
            FROM challenge_attempts existing
            WHERE existing.pid = data.pid
              AND existing.challenge = data.challenge
        )
    """
    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            execute_values(cursor, insert_sql, rows, page_size=1000)
            return cursor.rowcount


def bulk_insert_sqlite(db_path, rows):
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.executemany(
            """
            INSERT INTO challenge_attempts(pid, level, challenge, answer, correct, points, created_at)
            SELECT ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1
                FROM challenge_attempts existing
                WHERE existing.pid = ?
                  AND existing.challenge = ?
            )
            """,
            [row + (row[0], row[2]) for row in rows],
        )
        return cursor.rowcount


def verify_loadtest_users(expected_challenges):
    db.participant_stats.clear()
    db.leaderboard.clear()
    db.all_participants.clear()
    participants_after = db.all_participants()
    load_after = matching_loadtest_users()

    missing_users = []
    xp_bad = []
    record_counts = []
    for _, row in load_after.iterrows():
        pid = row["PID"]
        stats = db.participant_stats(pid)
        answered = set(stats["challenge"]) if not stats.empty else set()
        missing = expected_challenges - answered
        record_counts.append(len(stats))
        if missing:
            missing_users.append(f"{row['First name']}:{len(missing)}")
        xp = db.total_xp(pid)
        if xp != PERFECT_SCORE:
            xp_bad.append(f"{row['First name']}:{xp}")

    return participants_after, load_after, missing_users, xp_bad, record_counts


def main() -> int:
    os.chdir(APP_DIR)
    database_url = configured_database_url()
    db_path = os.path.join(APP_DIR, "stats_game.db")
    db.configure_database(db_path, database_url)
    db.ensure_schema.clear()
    db.ensure_schema()

    test_rows = matching_loadtest_users()
    attempts = loadtest_attempts()
    expected_challenges = {challenge for _, challenge, *_ in attempts}
    created_at = datetime.now().isoformat(timespec="seconds")
    rows = [
        (row["PID"], level, challenge, answer, 1 if correct else 0, points, created_at)
        for _, row in test_rows.iterrows()
        for level, challenge, answer, correct, points in attempts
    ]

    if database_url:
        inserted = bulk_insert_postgres(database_url, rows)
    else:
        inserted = bulk_insert_sqlite(db_path, rows)

    participants_after, load_after, missing_users, xp_bad, record_counts = verify_loadtest_users(
        expected_challenges
    )
    skipped = len(rows) - inserted

    print(f"database: {'postgres' if database_url else 'sqlite'}")
    print(f"load-test users: {len(load_after)}")
    print(f"expected challenge records per user: {len(expected_challenges)}")
    print(f"inserted new attempt rows: {inserted}")
    print(f"skipped existing rows: {skipped}")
    print(f"users missing any records: {', '.join(missing_users) if missing_users else 'none'}")
    print(f"users not at perfect XP: {', '.join(xp_bad) if xp_bad else 'none'}")
    if record_counts:
        print(f"min/max attempt records per load user: {min(record_counts)} / {max(record_counts)}")
    print(f"perfect XP: {PERFECT_SCORE}")
    print(f"total participants: {len(participants_after)}")
    return 0 if len(load_after) == 50 and not missing_users and not xp_bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
