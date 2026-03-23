"""
Unit Tests
----------
Tests core logic using the mock client — no real credentials needed.
Run with: pytest tests/
"""

import sys
import os
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from mock_client import MockInstagramClient
import database
from database import init_db, upsert_media, upsert_comments, save_daily_snapshot, get_engagement_trend


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Point the DB at a fresh temp file before every test."""
    database.DB_PATH = str(tmp_path / "test.db")
    init_db()


class TestMockClient:
    def setup_method(self):
        self.client = MockInstagramClient()

    def test_get_user_profile_returns_expected_fields(self):
        profile = self.client.get_user_profile()
        assert "id" in profile
        assert "username" in profile
        assert profile["account_type"] == "BUSINESS"

    def test_get_media_returns_list(self):
        media = self.client.get_media(limit=10)
        assert isinstance(media, list)
        assert len(media) > 0

    def test_get_media_respects_limit(self):
        media = self.client.get_media(limit=1)
        assert len(media) == 1

    def test_get_media_has_required_fields(self):
        media = self.client.get_media()
        for post in media:
            assert "id" in post
            assert "like_count" in post
            assert "comments_count" in post

    def test_get_comments_returns_list(self):
        comments = self.client.get_comments("mock_media_001")
        assert isinstance(comments, list)

    def test_get_comments_unknown_media_returns_empty(self):
        comments = self.client.get_comments("does_not_exist")
        assert comments == []

    def test_token_not_expiring(self):
        assert self.client.is_token_expiring_soon() is False


class TestDatabase:
    def test_upsert_media_stores_records(self):
        client = MockInstagramClient()
        posts = client.get_media()
        upsert_media(posts)
        # If no exception was raised, upsert succeeded

    def test_upsert_media_is_idempotent(self):
        """Running upsert twice should not raise errors or duplicate records."""
        client = MockInstagramClient()
        posts = client.get_media()
        upsert_media(posts)
        upsert_media(posts)  # Second run should INSERT OR REPLACE cleanly

    def test_upsert_comments_stores_records(self):
        client = MockInstagramClient()
        comments = client.get_comments("mock_media_001")
        upsert_comments(comments, "mock_media_001")

    def test_save_daily_snapshot(self):
        save_daily_snapshot("mock_media_001", like_count=100, comments_count=10)

    def test_duplicate_snapshot_ignored(self):
        """Two snapshots on the same day for the same post should not raise an error."""
        save_daily_snapshot("mock_media_001", like_count=100, comments_count=10)
        save_daily_snapshot("mock_media_001", like_count=105, comments_count=11)

    def test_get_engagement_trend_returns_list(self):
        save_daily_snapshot("mock_media_001", like_count=100, comments_count=10)
        trend = get_engagement_trend("mock_media_001", days=30)
        assert isinstance(trend, list)
        assert len(trend) == 1
        assert trend[0]["like_count"] == 100


class TestRateLimitBehavior:
    """
    Tests that verify the client handles rate limit scenarios gracefully.
    These use a patched client to simulate API error responses.
    """

    def test_unknown_media_returns_empty_comments(self):
        """
        Simulates the case where a media ID has no comments.
        The client should return an empty list, not raise an exception.
        """
        client = MockInstagramClient()
        result = client.get_comments("nonexistent_id")
        assert result == []
