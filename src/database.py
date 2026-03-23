"""
Database layer for storing Instagram engagement data.
Uses SQLite for portability — easy to swap for PostgreSQL in production
by updating the connection string and driver.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = "data/instagram.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dicts
    return conn


def init_db():
    """
    Create tables if they don't already exist.
    Safe to run on every startup — won't overwrite existing data.
    """
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS media (
                media_id        TEXT PRIMARY KEY,
                caption         TEXT,
                media_type      TEXT,
                timestamp       TEXT,
                like_count      INTEGER DEFAULT 0,
                comments_count  INTEGER DEFAULT 0,
                pulled_at       TEXT
            );

            CREATE TABLE IF NOT EXISTS comments (
                comment_id  TEXT PRIMARY KEY,
                media_id    TEXT,
                username    TEXT,
                text        TEXT,
                timestamp   TEXT,
                pulled_at   TEXT,
                FOREIGN KEY (media_id) REFERENCES media(media_id)
            );

            CREATE TABLE IF NOT EXISTS daily_snapshots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id        TEXT,
                snapshot_date   TEXT,
                like_count      INTEGER,
                comments_count  INTEGER,
                UNIQUE(media_id, snapshot_date)
            );
        """)
    logger.info("Database initialized.")


def upsert_media(posts: list):
    """
    Insert or update media records.
    Uses INSERT OR REPLACE so re-running a pull never creates duplicates.
    """
    pulled_at = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO media
                (media_id, caption, media_type, timestamp, like_count, comments_count, pulled_at)
            VALUES
                (:id, :caption, :media_type, :timestamp, :like_count, :comments_count, :pulled_at)
            """,
            [{**post, "pulled_at": pulled_at} for post in posts],
        )
    logger.info(f"Upserted {len(posts)} media records.")


def upsert_comments(comments: list, media_id: str):
    """Insert or update comments for a given media post."""
    pulled_at = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO comments
                (comment_id, media_id, username, text, timestamp, pulled_at)
            VALUES
                (:id, :media_id, :username, :text, :timestamp, :pulled_at)
            """,
            [{**c, "media_id": media_id, "pulled_at": pulled_at} for c in comments],
        )
    logger.info(f"Upserted {len(comments)} comments for media {media_id}.")


def save_daily_snapshot(media_id: str, like_count: int, comments_count: int):
    """
    Record a daily engagement snapshot for trend tracking.
    UNIQUE constraint on (media_id, date) prevents duplicate snapshots
    if the job is accidentally run twice in one day.
    """
    today = datetime.utcnow().date().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO daily_snapshots
                (media_id, snapshot_date, like_count, comments_count)
            VALUES (?, ?, ?, ?)
            """,
            (media_id, today, like_count, comments_count),
        )
    logger.info(f"Snapshot saved for {media_id} on {today}.")


def get_engagement_trend(media_id: str, days: int = 30) -> list:
    """Fetch the last N days of engagement snapshots for a media post."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT snapshot_date, like_count, comments_count
            FROM daily_snapshots
            WHERE media_id = ?
            ORDER BY snapshot_date DESC
            LIMIT ?
            """,
            (media_id, days),
        ).fetchall()
    return [dict(row) for row in rows]
