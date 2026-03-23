"""
CSV Report Generator
--------------------
Generates a clean CSV report from stored engagement data.
Two sections per report:
  1. Per-post rows  — one row per media post
  2. Account summary — totals and averages across all posts

Run manually:  python src/report.py
Output:        data/engagement_report_YYYY-MM-DD.csv
"""

import csv
import logging
import os
from datetime import datetime
from database import get_connection, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPORTS_DIR = "data"


def generate_report() -> str:
    """
    Pulls all media and latest engagement counts from the database
    and writes them to a dated CSV file.

    Returns the path to the generated file.
    """
    init_db()

    today = datetime.utcnow().date().isoformat()
    filename = f"engagement_report_{today}.csv"
    filepath = os.path.join(REPORTS_DIR, filename)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # --- Fetch all media records ---
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                media_id,
                caption,
                media_type,
                timestamp,
                like_count,
                comments_count,
                pulled_at
            FROM media
            ORDER BY timestamp DESC
        """).fetchall()

    if not rows:
        logger.warning("No media records found in the database. Run the pull job first.")
        return ""

    posts = [dict(row) for row in rows]

    # --- Calculate account-level summary ---
    total_likes    = sum(p["like_count"] for p in posts)
    total_comments = sum(p["comments_count"] for p in posts)
    total_posts    = len(posts)
    avg_likes      = round(total_likes / total_posts, 1)
    avg_comments   = round(total_comments / total_posts, 1)
    top_post       = max(posts, key=lambda p: p["like_count"])

    # --- Write CSV ---
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # -- Section 1: Per-post data --
        writer.writerow([
            "SECTION",
            "Media ID",
            "Media Type",
            "Posted At",
            "Caption (truncated)",
            "Like Count",
            "Comment Count",
            "Data Captured At",
        ])

        for post in posts:
            caption = (post["caption"] or "")[:80]
            if len(post["caption"] or "") > 80:
                caption += "..."
            writer.writerow([
                "POST",
                post["media_id"],
                post["media_type"],
                post["timestamp"],
                caption,
                post["like_count"],
                post["comments_count"],
                post["pulled_at"],
            ])

        # Blank row between sections
        writer.writerow([])

        # -- Section 2: Account summary --
        writer.writerow(["SECTION", "Metric", "Value"])
        writer.writerow(["SUMMARY", "Report Date",           today])
        writer.writerow(["SUMMARY", "Total Posts Analyzed",  total_posts])
        writer.writerow(["SUMMARY", "Total Likes",           total_likes])
        writer.writerow(["SUMMARY", "Total Comments",        total_comments])
        writer.writerow(["SUMMARY", "Average Likes/Post",    avg_likes])
        writer.writerow(["SUMMARY", "Average Comments/Post", avg_comments])
        writer.writerow(["SUMMARY", "Top Post (by likes)",   top_post["media_id"]])
        writer.writerow(["SUMMARY", "Top Post Like Count",   top_post["like_count"]])

    logger.info(f"Report written to {filepath}")
    return filepath


if __name__ == "__main__":
    path = generate_report()
    if path:
        print(f"\nReport saved to: {path}\n")