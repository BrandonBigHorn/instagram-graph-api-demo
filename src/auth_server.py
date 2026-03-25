"""
OAuth Callback Handler
----------------------
Handles BOTH Instagram Login and Facebook Login OAuth flows.

Instagram Login  — for accounts NOT linked to a Facebook Page
Facebook Login   — for accounts linked to a Facebook Page (like MuzicCoin)

Set AUTH_FLOW in your .env file:
  AUTH_FLOW=instagram  (default)
  AUTH_FLOW=facebook   (use this for MuzicCoin/Anthony)
"""

import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv, set_key
from instagram_client import InstagramClient
from facebook_client import FacebookLoginClient

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

APP_ID       = os.getenv("INSTAGRAM_APP_ID")
APP_SECRET   = os.getenv("INSTAGRAM_APP_SECRET")
REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/callback")
AUTH_FLOW    = os.getenv("AUTH_FLOW", "instagram").lower()
ENV_FILE     = os.path.join(os.path.dirname(__file__), "../.env")


@app.route("/")
def index():
    return jsonify({
        "status": "Auth server is running.",
        "auth_flow": AUTH_FLOW,
        "redirect_uri": REDIRECT_URI
    })


@app.route("/callback")
def callback():
    error = request.args.get("error")
    if error:
        reason = request.args.get("error_reason", "unknown")
        logger.error(f"User denied authorization. Reason: {reason}")
        return f"""
            <h2>Authorization Denied</h2>
            <p>Reason: {reason}</p>
            <p>Please try again.</p>
        """, 400

    code = request.args.get("code")
    if not code:
        logger.error("No code received in callback.")
        return "<h2>Error</h2><p>No authorization code received.</p>", 400

    logger.info(f"Authorization code received via {AUTH_FLOW} flow.")

    if AUTH_FLOW == "facebook":
        return handle_facebook_callback(code)

    return handle_instagram_callback(code)


def handle_instagram_callback(code: str):
    try:
        token_data = InstagramClient.exchange_short_lived_token(
            app_id=APP_ID,
            app_secret=APP_SECRET,
            short_lived_token=code,
        )
    except Exception as e:
        logger.error(f"Instagram token exchange failed: {e}")
        return f"<h2>Token Exchange Failed</h2><p>{e}</p>", 500

    access_token = token_data.get("access_token")
    expires_in   = token_data.get("expires_in", 0)
    days         = round(expires_in / 86400)

    if not access_token:
        return "<h2>Error</h2><p>No access token in response.</p>", 500

    save_token(access_token)
    logger.info(f"Instagram token saved. Expires in ~{days} days.")
    return success_page(days, "Instagram")


def handle_facebook_callback(code: str):
    try:
        token_data = FacebookLoginClient.exchange_code_for_token(
            app_id=APP_ID,
            app_secret=APP_SECRET,
            code=code,
            redirect_uri=REDIRECT_URI,
        )
    except Exception as e:
        logger.error(f"Facebook token exchange failed: {e}")
        return f"<h2>Token Exchange Failed</h2><p>{e}</p>", 500

    access_token = token_data.get("access_token")
    expires_in   = token_data.get("expires_in", 0)
    days         = round(expires_in / 86400)

    if not access_token:
        return "<h2>Error</h2><p>No access token in response.</p>", 500

    # Auto-discover Instagram Business Account ID
    try:
        fb_client = FacebookLoginClient(access_token=access_token)
        pages = fb_client.get_facebook_pages()
        ig_account_id = None

        for page in pages:
            page_id = page.get("id")
            ig_id = fb_client.get_instagram_account_id(page_id)
            if ig_id:
                ig_account_id = ig_id
                break

        if ig_account_id:
            set_key(ENV_FILE, "INSTAGRAM_ACCOUNT_ID", ig_account_id)
            logger.info(f"Instagram Account ID saved: {ig_account_id}")

    except Exception as e:
        logger.warning(f"Could not auto-discover Instagram account ID: {e}")

    save_token(access_token)
    logger.info(f"Facebook token saved. Expires in ~{days} days.")
    return success_page(days, "Facebook")


def save_token(access_token: str):
    try:
        set_key(ENV_FILE, "INSTAGRAM_ACCESS_TOKEN", access_token)
        logger.info("Access token saved to .env successfully.")
    except Exception as e:
        logger.warning(f"Could not auto-save token: {e}")
        logger.info(f"Manual save needed. Token: {access_token}")


def success_page(days: int, flow: str) -> str:
    return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 20px;">
            <h2 style="color: #2e7d32;">Authorization Successful</h2>
            <p>The Instagram account has been connected successfully via {flow} Login.</p>
            <p><strong>Token expires in:</strong> ~{days} days</p>
            <p>The access token has been saved automatically. You can now run the pull job.</p>
            <hr>
            <p style="color: #888; font-size: 13px;">
                You can close this window. The auth server can be stopped with Ctrl+C.
            </p>
        </body>
        </html>
    """


if __name__ == "__main__":
    if not APP_ID or not APP_SECRET:
        raise EnvironmentError(
            "INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET must be set in your .env file."
        )
    logger.info(f"Auth server starting on http://localhost:8000")
    logger.info(f"Auth flow: {AUTH_FLOW.upper()}")
    logger.info(f"Redirect URI: {REDIRECT_URI}")
    app.run(host="0.0.0.0", port=8000, debug=False)