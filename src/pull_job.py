"""
Daily Engagement Pull Job
-------------------------
Supports both Instagram Login and Facebook Login flows.
Set AUTH_FLOW in your .env to control which client is used:
  AUTH_FLOW=instagram  (default)
  AUTH_FLOW=facebook   (for accounts linked to a Facebook Page)
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv

from instagram_client import InstagramClient, InstagramAPIError
from facebook_client import FacebookLoginClient, FacebookAPIError
from database import init_db, upsert_media, upsert_comments, save_daily_snapshot

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_pull():
    logger.info("=" * 50)
    logger.info(f"Pull job started at {datetime.utcnow().isoformat()}")
    logger.info("=" * 50)

    init_db()

    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    auth_flow    = os.getenv("AUTH_FLOW", "instagram").lower()

    if not access_token:
        raise EnvironmentError("INSTAGRAM_ACCESS_TOKEN not set. Check your .env file.")

    if auth_flow == "facebook":
        ig_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        if not ig_account_id:
            raise EnvironmentError(
                "INSTAGRAM_ACCOUNT_ID not set. "
                "Run the auth flow first to auto-discover it."
            )
        client = FacebookLoginClient(
            access_token=access_token,
            instagram_account_id=ig_account_id
        )
        logger.info("Using Facebook Login client.")
    else:
        client = InstagramClient(access_token=access_token)
        logger.info("Using Instagram Login client.")

    try:
        profile = client.get_user_profile()
        logger.info(f"Authenticated as @{profile.get('username')} (ID: {profile.get('id')})")
    except (InstagramAPIError, FacebookAPIError) as e:
        logger.error(f"Authentication failed: {e}")
        return

    try:
        posts = client.get_media(limit=20)
        logger.info(f"Fetched {len(posts)} media posts.")
    except (InstagramAPIError, FacebookAPIError) as e:
        logger.error(f"Failed to fetch media: {e}")
        return

    if not posts:
        logger.info("No media found for this account. Exiting.")
        return

    upsert_media(posts)

    for post in posts:
        media_id       = post["id"]
        like_count     = post.get("like_count", 0)
        comments_count = post.get("comments_count", 0)

        save_daily_snapshot(media_id, like_count, comments_count)

        try:
            comments = client.get_comments(media_id)
            if comments:
                upsert_comments(comments, media_id)
        except (InstagramAPIError, FacebookAPIError) as e:
            logger.warning(f"Could not fetch comments for {media_id}: {e}")
            continue

    logger.info("Pull job completed successfully.")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_pull()
