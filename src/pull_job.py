"""
Daily Engagement Pull Job
-------------------------
Pulls the latest likes and comments for all recent media posts
and stores snapshots in the local database.

Run manually:      python src/pull_job.py
Run on a schedule: cron, APScheduler, or a cloud task runner (e.g. AWS Lambda + EventBridge)

Cron example (runs every day at 8am UTC):
    0 8 * * * /usr/bin/python3 /path/to/src/pull_job.py >> /var/log/instagram_pull.log 2>&1
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv

from instagram_client import InstagramClient, InstagramAPIError
from database import init_db, upsert_media, upsert_comments, save_daily_snapshot

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_pull():
    logger.info("=" * 50)
    logger.info(f"Pull job started at {datetime.utcnow().isoformat()}")
    logger.info("=" * 50)

    # --- Init ---
    init_db()

    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not access_token:
        raise EnvironmentError("INSTAGRAM_ACCESS_TOKEN not set. Check your .env file.")

    client = InstagramClient(access_token=access_token)

    # --- Profile check ---
    try:
        profile = client.get_user_profile()
        logger.info(f"Authenticated as @{profile.get('username')} (ID: {profile.get('id')})")
    except InstagramAPIError as e:
        logger.error(f"Authentication failed: {e}")
        return

    # --- Pull recent media ---
    try:
        posts = client.get_media(limit=20)
        logger.info(f"Fetched {len(posts)} media posts.")
    except InstagramAPIError as e:
        logger.error(f"Failed to fetch media: {e}")
        return

    if not posts:
        logger.info("No media found for this account. Exiting.")
        return

    # --- Store media records ---
    upsert_media(posts)

    # --- Pull comments + save daily snapshots ---
    for post in posts:
        media_id = post["id"]
        like_count = post.get("like_count", 0)
        comments_count = post.get("comments_count", 0)

        # Daily snapshot for trend tracking
        save_daily_snapshot(media_id, like_count, comments_count)

        # Pull and store comments
        try:
            comments = client.get_comments(media_id)
            if comments:
                upsert_comments(comments, media_id)
        except InstagramAPIError as e:
            # Log and continue — don't let one failed post kill the whole job
            logger.warning(f"Could not fetch comments for {media_id}: {e}")
            continue

    logger.info("Pull job completed successfully.")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_pull()
