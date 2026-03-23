"""
Instagram Graph API Client
Handles authentication, token management, and API requests
with built-in rate limit handling and exponential backoff.

Scopes updated January 2025 - old scope values (business_basic, etc.)
were deprecated on January 27, 2025. This client uses the current
required scope values for Instagram API with Instagram Login.
"""

import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Current required scopes for Instagram API with Instagram Login
# Ref: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login
# Old values (deprecated Jan 27 2025): business_basic, business_manage_comments
SCOPES = [
    "instagram_business_basic",            # Read profile and media
    "instagram_business_manage_comments",  # Read and manage comments
]


class InstagramClient:
    BASE_URL = "https://graph.instagram.com/v21.0"  # Latest stable version as of 2025

    def __init__(self, access_token: str, token_expiry: Optional[datetime] = None):
        self.access_token = access_token
        self.token_expiry = token_expiry
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # OAuth Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def build_auth_url(app_id: str, redirect_uri: str) -> str:
        """
        Builds the OAuth authorization URL to send to the account owner.
        They visit this URL, log in with Instagram, and approve the requested scopes.
        After approval, Instagram redirects them to redirect_uri with a short-lived code.

        Required scopes use the new names (post Jan 27 2025):
          - instagram_business_basic
          - instagram_business_manage_comments
        """
        params = {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "scope": ",".join(SCOPES),
            "response_type": "code",
        }
        url = f"https://api.instagram.com/oauth/authorize?{urlencode(params)}"
        logger.info(f"Auth URL built for app {app_id}")
        return url

    # ------------------------------------------------------------------
    # Token Management
    # ------------------------------------------------------------------

    def is_token_expiring_soon(self, buffer_days: int = 5) -> bool:
        """
        Returns True if the token expires within the buffer window.
        We refresh proactively so the app never fails mid-run.
        """
        if not self.token_expiry:
            return False
        return datetime.utcnow() >= (self.token_expiry - timedelta(days=buffer_days))

    def refresh_long_lived_token(self) -> dict:
        """
        Exchanges the current long-lived token for a fresh one.
        Long-lived tokens last 60 days. Refreshing resets the clock.
        Call this on a schedule (e.g. every 50 days) to stay authenticated.
        """
        logger.info("Refreshing long-lived access token...")
        url = "https://graph.instagram.com/refresh_access_token"
        params = {
            "grant_type": "ig_refresh_token",
            "access_token": self.access_token,
        }
        response = self._request("GET", url, params=params)
        self.access_token = response["access_token"]
        self.token_expiry = datetime.utcnow() + timedelta(seconds=response["expires_in"])
        logger.info(f"Token refreshed. New expiry: {self.token_expiry.date()}")
        return response

    @staticmethod
    def exchange_short_lived_token(app_id: str, app_secret: str, short_lived_token: str) -> dict:
        """
        Exchanges a short-lived token (1 hour) for a long-lived token (60 days).
        This is the first step after a user completes the OAuth flow.

        Instagram API with Instagram Login token exchange endpoint.
        """
        logger.info("Exchanging short-lived token for long-lived token...")
        url = "https://graph.instagram.com/access_token"
        params = {
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": short_lived_token,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        logger.info("Token exchange successful.")
        return data

    # ------------------------------------------------------------------
    # Data Endpoints
    # ------------------------------------------------------------------

    def get_user_profile(self) -> dict:
        """Fetch basic profile info for the authenticated Business/Creator account."""
        url = f"{self.BASE_URL}/me"
        return self._request("GET", url, params={"fields": "id,username,account_type,media_count"})

    def get_media(self, limit: int = 10) -> list:
        """
        Fetch recent media posts for the account.
        Returns a list of media objects with id, caption, type, and timestamp.
        Requires: instagram_business_basic scope
        """
        url = f"{self.BASE_URL}/me/media"
        params = {
            "fields": "id,caption,media_type,timestamp,like_count,comments_count",
            "limit": limit,
        }
        response = self._request("GET", url, params=params)
        return response.get("data", [])

    def get_media_insights(self, media_id: str) -> dict:
        """
        Fetch engagement insights for a specific media post.
        Returns impressions, reach, likes, comments, saves, and shares.
        Requires: instagram_business_basic scope
        """
        url = f"{self.BASE_URL}/{media_id}/insights"
        params = {
            "metric": "impressions,reach,likes,comments,saves,shares",
        }
        return self._request("GET", url, params=params)

    def get_comments(self, media_id: str) -> list:
        """
        Fetch all comments for a specific media post.
        Requires: instagram_business_manage_comments scope
        """
        url = f"{self.BASE_URL}/{media_id}/comments"
        params = {"fields": "id,text,timestamp,username"}
        response = self._request("GET", url, params=params)
        return response.get("data", [])

    # ------------------------------------------------------------------
    # Request Handler - Rate Limiting + Exponential Backoff
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        max_retries: int = 4,
    ) -> dict:
        """
        Central request handler with exponential backoff for rate limit errors.

        Instagram Graph API rate limits are based on the number of active users
        connected to your app. When you hit the limit, the API returns a 429 or
        error code 4/17/32/613. We back off and retry rather than crashing.

        Backoff schedule: 2s -> 4s -> 8s -> 16s
        """
        if params is None:
            params = {}

        # Always inject the access token
        params["access_token"] = self.access_token

        # Proactive token refresh check before every request
        if self.is_token_expiring_soon():
            logger.warning("Token expiring soon - consider refreshing before the next run.")

        rate_limit_codes = {4, 17, 32, 80001, 80006, 613}

        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, params=params, timeout=15)
                data = response.json()

                # Check for API-level errors inside a 200 response
                if "error" in data:
                    error = data["error"]
                    code = error.get("code")
                    message = error.get("message", "Unknown error")

                    if code in rate_limit_codes:
                        wait = 2 ** (attempt + 1)
                        logger.warning(
                            f"Rate limit hit (code {code}). "
                            f"Backing off {wait}s before retry {attempt + 1}/{max_retries}..."
                        )
                        time.sleep(wait)
                        continue

                    raise InstagramAPIError(f"API error {code}: {message}")

                response.raise_for_status()
                return data

            except requests.exceptions.Timeout:
                wait = 2 ** (attempt + 1)
                logger.warning(f"Request timed out. Retrying in {wait}s...")
                time.sleep(wait)

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                raise

        raise InstagramAPIError(f"Request failed after {max_retries} retries.")


class InstagramAPIError(Exception):
    """Raised when the Instagram Graph API returns an error response."""
    pass