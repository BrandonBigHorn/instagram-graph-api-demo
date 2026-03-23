"""
Demo Runner
-----------
Runs the full pull pipeline using mock data so you can see
exactly how the system works without needing Instagram credentials.

Run with: python demo.py
"""

import sys
import os
sys.path.insert(0, "src")

import database
database.DB_PATH = "data/demo.db"

from mock_client import MockInstagramClient
from database import init_db, upsert_media, upsert_comments, save_daily_snapshot, get_engagement_trend

def run_demo():
    print("\n" + "=" * 55)
    print("  Instagram Graph API Demo — Mock Pipeline Run")
    print("=" * 55)

    init_db()
    client = MockInstagramClient()

    # Profile
    profile = client.get_user_profile()
    print(f"\n✅ Authenticated as @{profile['username']}")
    print(f"   Account type : {profile['account_type']}")
    print(f"   Media count  : {profile['media_count']}")

    # Media pull
    posts = client.get_media()
    print(f"\n📸 Pulled {len(posts)} media posts:")
    for post in posts:
        print(f"   [{post['media_type']}] {post['id']} — "
              f"❤️  {post['like_count']} likes, 💬 {post['comments_count']} comments")

    # Store media
    upsert_media(posts)
    print("\n💾 Media records saved to database.")

    # Comments + snapshots
    print("\n💬 Pulling comments and saving daily snapshots...")
    for post in posts:
        media_id = post["id"]
        save_daily_snapshot(media_id, post["like_count"], post["comments_count"])
        comments = client.get_comments(media_id)
        if comments:
            upsert_comments(comments, media_id)
            print(f"   {media_id}: {len(comments)} comment(s) stored.")
        else:
            print(f"   {media_id}: no comments.")

    # Trend sample
    print("\n📊 Engagement trend for mock_media_001:")
    trend = get_engagement_trend("mock_media_001", days=30)
    for row in trend:
        print(f"   {row['snapshot_date']} — ❤️  {row['like_count']} | 💬 {row['comments_count']}")

    print("\n✅ Demo complete. Database written to data/demo.db")
    print("=" * 55 + "\n")

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    run_demo()
