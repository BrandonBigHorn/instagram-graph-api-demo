"""
Facebook Login Instagram Client
---------------------------------
Used when the Instagram Business account is linked to a Facebook Page.
This flow uses the Facebook Graph API instead of the Instagram Graph API.

Auth flow:
  1. User visits the Facebook OAuth URL
  2. They approve the app on Facebook
  3. Facebook redirects to your callback with a short-lived code
  4. Code is exchanged for a long-lived token (60 days)
  5. Token is used to pull Instagram media and engagement data
     via the Facebook Graph API endpoint
"""

import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Scopes required for Facebook Login flow
# These are different from the Instagram Login scopes
FB_SCOPES = [
    "instagram_basic",           # Read Instagram profile and media
    "instagram_manage_comments", # Read comments on media
    "pages_show_list",           # List Facebook Pages the user manages
    "pages_read_engagement",     # Read engagement data on Pages
]


class FacebookLoginClient:
    """
    Instagram API client for accounts linked to a Facebook Page.
    Uses the Facebook Graph API (graph.facebook.com) instead of
    the Instagram Graph API (graph.instagram.com).
    """
    BASE_URL = "https://graph.facebook.com/v21.0"

    def __init__(self, access_token: str, instagram_account_id: Optional[str] = None):
        self.access_token = access_token
        self.instagram_account_id = instagram_account_id
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # OAuth Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def build_auth_url(app_id: str, redirect_uri: str) -> str:
        """
        Builds the Facebook OAuth authorization URL.
        User visits this URL, logs in with Facebook, and approves the app.
        Facebook then redirects to redirect_uri with a short-lived code.
        """
        params = {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "scope": ",".join(FB_SCOPES),
            "response_type": "code",
        }
        url = f"https://www.facebook.com/dialog/oauth?{urlencode(params)}"
        logger.info(f"Facebook auth URL built for app {app_id}")
        return url

    @staticmethod
    def exchange_code_for_token(app_id: str, app_secret: str, code: str, redirect_uri: str) -> dict:
        """
        Exchanges a short-lived code for a short-lived access token.
        Then exchanges that for a long-lived token (60 days).
        """
        logger.info("Exchanging code for short-lived token...")

        # Step 1: Code -> short-lived token
        url = "https://graph.facebook.com/v21.0/oauth/access_token"
        params = {
            "client_id": app_id,
            "client_secret": app_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        short_lived_data = response.json()
        short_lived_token = short_lived_data.get("access_token")

        if not short_lived_token:
            raise FacebookAPIError(f"No short-lived token in response: {short_lived_data}")

        logger.info("Short-lived token received. Exchanging for long-lived token...")

        # Step 2: Short-lived -> long-lived token (60 days)
        ll_url = "https://graph.facebook.com/v21.0/oauth/access_token"
        ll_params = {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_lived_token,
        }
        ll_response = requests.get(ll_url, params=ll_params)
        ll_response.raise_for_status()
        data = ll_response.json()
        logger.info("Long-lived token received successfully.")
        return data

    # ------------------------------------------------------------------
    # Account Setup
    # ------------------------------------------------------------------

    def get_facebook_pages(self) -> list:
        """
        Fetches all Facebook Pages the authenticated user manages.
        Returns a list of pages with id, name, and access_token.
        """
        url = f"{self.BASE_URL}/me/accounts"
        response = self._request("GET", url)
        return response.get("data", [])

    def get_instagram_account_id(self, page_id: str) -> Optional[str]:
        """
        Gets the Instagram Business Account ID linked to a Facebook Page.
        Must be called before pulling Instagram data.
        """
        url = f"{self.BASE_URL}/{page_id}"
        params = {"fields": "instagram_business_account"}
        response = self._request("GET", url, params=params)
        ig_account = response.get("instagram_business_account")
        if ig_account:
            self.instagram_account_id = ig_account.get("id")
            logger.info(f"Instagram account ID found: {self.instagram_account_id}")
            return self.instagram_account_id
        return None

    # ------------------------------------------------------------------
    # Data Endpoints
    # ------------------------------------------------------------------

    def get_user_profile(self) -> dict:
        """Fetch basic profile info for the Instagram Business account."""
        if not self.instagram_account_id:
            raise FacebookAPIError("Instagram account ID not set. Call get_instagram_account_id() first.")
        url = f"{self.BASE_URL}/{self.instagram_account_id}"
        return self._request("GET", url, params={
            "fields": "id,username,account_type,media_count"
        })

    def get_media(self, limit: int = 10) -> list:
        """
        Fetch recent media posts for the Instagram Business account.
        Requires: instagram_basic scope
        """
        if not self.instagram_account_id:
            raise FacebookAPIError("Instagram account ID not set. Call get_instagram_account_id() first.")
        url = f"{self.BASE_URL}/{self.instagram_account_id}/media"
        params = {
            "fields": "id,caption,media_type,timestamp,like_count,comments_count",
            "limit": limit,
        }
        response = self._request("GET", url, params=params)
        return response.get("data", [])

    def get_comments(self, media_id: str) -> list:
        """
        Fetch comments for a specific media post.
        Requires: instagram_manage_comments scope
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
        if params is None:
            params = {}

        params["access_token"] = self.access_token
        rate_limit_codes = {4, 17, 32, 80001, 80006, 613}

        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, params=params, timeout=15)
                data = response.json()

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

                    raise FacebookAPIError(f"API error {code}: {message}")

                response.raise_for_status()
                return data

            except requests.exceptions.Timeout:
                wait = 2 ** (attempt + 1)
                logger.warning(f"Request timed out. Retrying in {wait}s...")
                time.sleep(wait)

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                raise

        raise FacebookAPIError(f"Request failed after {max_retries} retries.")


class FacebookAPIError(Exception):
    """Raised when the Facebook Graph API returns an error response."""
    pass