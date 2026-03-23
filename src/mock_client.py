"""
Mock Instagram API Client
--------------------------
Simulates the Instagram Graph API responses using realistic fake data.
Use this for demos, local development, and unit tests without
needing real credentials or a live Instagram account.

Swap InstagramClient for MockInstagramClient in pull_job.py to run
the full pipeline against mock data.
"""

from datetime import datetime, timedelta
import random


MOCK_MEDIA = [
    {
        "id": "mock_media_001",
        "caption": "Excited to share our latest product launch! #newproduct #launch",
        "media_type": "IMAGE",
        "timestamp": (datetime.utcnow() - timedelta(days=1)).isoformat(),
        "like_count": 142,
        "comments_count": 18,
    },
    {
        "id": "mock_media_002",
        "caption": "Behind the scenes look at our team 🎉 #team #culture",
        "media_type": "IMAGE",
        "timestamp": (datetime.utcnow() - timedelta(days=3)).isoformat(),
        "like_count": 89,
        "comments_count": 11,
    },
    {
        "id": "mock_media_003",
        "caption": "Weekly tip: consistency is key. What are your goals this week?",
        "media_type": "VIDEO",
        "timestamp": (datetime.utcnow() - timedelta(days=7)).isoformat(),
        "like_count": 214,
        "comments_count": 34,
    },
]

MOCK_COMMENTS = {
    "mock_media_001": [
        {"id": "c001", "username": "user_alpha", "text": "Love this!", "timestamp": datetime.utcnow().isoformat()},
        {"id": "c002", "username": "user_beta",  "text": "So cool 🔥",  "timestamp": datetime.utcnow().isoformat()},
    ],
    "mock_media_002": [
        {"id": "c003", "username": "user_gamma", "text": "Great team!", "timestamp": datetime.utcnow().isoformat()},
    ],
    "mock_media_003": [
        {"id": "c004", "username": "user_delta", "text": "Very helpful tip.", "timestamp": datetime.utcnow().isoformat()},
        {"id": "c005", "username": "user_echo",  "text": "Thanks for sharing!", "timestamp": datetime.utcnow().isoformat()},
    ],
}


class MockInstagramClient:
    """Drop-in replacement for InstagramClient that returns mock data."""

    def get_user_profile(self) -> dict:
        return {
            "id": "mock_user_123",
            "username": "demo_business_account",
            "account_type": "BUSINESS",
            "media_count": len(MOCK_MEDIA),
        }

    def get_media(self, limit: int = 10) -> list:
        # Simulate slight engagement variance on each call (like a real account)
        media = []
        for post in MOCK_MEDIA[:limit]:
            media.append({
                **post,
                "like_count": post["like_count"] + random.randint(0, 5),
                "comments_count": post["comments_count"] + random.randint(0, 2),
            })
        return media

    def get_comments(self, media_id: str) -> list:
        return MOCK_COMMENTS.get(media_id, [])

    def is_token_expiring_soon(self, buffer_days: int = 5) -> bool:
        return False  # Mock tokens never expire
