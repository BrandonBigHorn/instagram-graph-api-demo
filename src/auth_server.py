"""
OAuth Callback Handler
----------------------
Handles Facebook Login OAuth flow for MuzicCoin/Anthony.

Deployed on Render.com with a permanent HTTPS URL.
Anthony clicks /login, approves on Facebook, token is saved automatically.

ENV variables required (set in Render dashboard):
  INSTAGRAM_APP_ID
  INSTAGRAM_APP_SECRET
  INSTAGRAM_REDIRECT_URI   -> https://your-app.onrender.com/callback
  AUTH_FLOW                -> facebook
"""

import os
import sys
import logging
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, redirect
from dotenv import load_dotenv

# Allow imports from the src/ directory regardless of where gunicorn is launched from
sys.path.insert(0, os.path.dirname(__file__))

from instagram_client import InstagramClient
from facebook_client import FacebookLoginClient

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

APP_ID       = os.getenv("INSTAGRAM_APP_ID")
APP_SECRET   = os.getenv("INSTAGRAM_APP_SECRET")
REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/callback")
AUTH_FLOW    = os.getenv("AUTH_FLOW", "facebook").lower()
DB_PATH      = os.getenv("DB_PATH", "data/instagram.db")


# ------------------------------------------------------------------
# Token Storage — saves to SQLite so it survives Render restarts
# ------------------------------------------------------------------

def save_token_to_db(access_token: str, ig_account_id: str = None):
    """
    Saves the access token and Instagram account ID to a tokens table.
    Creates the table if it doesn't exist.
    Safe to call multiple times — always overwrites the single token row.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id              INTEGER PRIMARY KEY,
            access_token    TEXT NOT NULL,
            ig_account_id   TEXT,
            saved_at        TEXT
        )
    """)
    conn.execute("DELETE FROM tokens")  # Only ever keep one active token
    conn.execute(
        "INSERT INTO tokens (access_token, ig_account_id, saved_at) VALUES (?, ?, ?)",
        (access_token, ig_account_id, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    logger.info("Token saved to database successfully.")


def load_token_from_db() -> dict:
    """Loads the current token from the database. Returns None if not found."""
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT access_token, ig_account_id, saved_at FROM tokens LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            return {"access_token": row[0], "ig_account_id": row[1], "saved_at": row[2]}
    except Exception:
        pass
    return None


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.route("/")
def index():
    """Health check — confirms the server is running."""
    return jsonify({
        "status": "Auth server is running.",
        "auth_flow": AUTH_FLOW,
        "redirect_uri": REDIRECT_URI
    })


@app.route("/login")
def login():
    """
    The one link Anthony needs to click.
    Redirects him straight to Facebook's OAuth login page.
    No configuration, no copy-pasting — just a login screen he recognizes.
    """
    if not APP_ID:
        return "<h2>Configuration Error</h2><p>INSTAGRAM_APP_ID is not set on the server.</p>", 500

    auth_url = FacebookLoginClient.build_auth_url(
        app_id=APP_ID,
        redirect_uri=REDIRECT_URI
    )
    logger.info("Redirecting user to Facebook OAuth login page.")
    return redirect(auth_url)


@app.route("/callback")
def callback():
    """
    Facebook redirects here after Anthony approves (or denies) the app.
    Exchanges the code for a token and saves everything automatically.
    """
    error = request.args.get("error")
    if error:
        reason = request.args.get("error_reason", "unknown")
        logger.error(f"User denied authorization. Reason: {reason}")
        return """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 20px;">
                <h2 style="color: #c62828;">Authorization Denied</h2>
                <p>It looks like the app was not approved. Please try clicking the login link again.</p>
                <p>If the problem continues, contact Brandon.</p>
            </body>
            </html>
        """, 400

    code = request.args.get("code")
    if not code:
        logger.error("No code received in callback.")
        return "<h2>Error</h2><p>No authorization code received from Facebook.</p>", 400

    logger.info("Authorization code received. Starting token exchange...")
    return handle_facebook_callback(code)


def handle_facebook_callback(code: str):
    """
    Exchanges the auth code for a long-lived token,
    auto-discovers the Instagram Business Account ID,
    and saves everything to the database.
    """
    # Step 1: Exchange code for long-lived token
    try:
        token_data = FacebookLoginClient.exchange_code_for_token(
            app_id=APP_ID,
            app_secret=APP_SECRET,
            code=code,
            redirect_uri=REDIRECT_URI,
        )
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return f"<h2>Token Exchange Failed</h2><p>{e}</p>", 500

    access_token = token_data.get("access_token")
    expires_in   = token_data.get("expires_in", 0)
    days         = round(expires_in / 86400)

    if not access_token:
        return "<h2>Error</h2><p>No access token returned from Facebook.</p>", 500

    # Step 2: Auto-discover Instagram Business Account ID from linked Facebook Page
    ig_account_id = None
    try:
        fb_client = FacebookLoginClient(access_token=access_token)
        pages = fb_client.get_facebook_pages()

        for page in pages:
            page_id = page.get("id")
            ig_id = fb_client.get_instagram_account_id(page_id)
            if ig_id:
                ig_account_id = ig_id
                logger.info(f"Instagram Account ID discovered: {ig_account_id}")
                break

        if not ig_account_id:
            logger.warning("No Instagram Business Account found linked to Facebook Pages.")

    except Exception as e:
        logger.warning(f"Could not auto-discover Instagram account ID: {e}")

    # Step 3: Save token to database
    save_token_to_db(access_token, ig_account_id)
    logger.info(f"Facebook token saved. Expires in ~{days} days.")

    # Step 4: Show success page with token displayed for Brandon to copy
    return success_page(days, access_token, ig_account_id)


def success_page(days: int, access_token: str, ig_account_id: str) -> str:
    """
    What Anthony sees after approving — a simple success message.
    Also displays the token and account ID clearly for Brandon to copy
    from his server logs or Render dashboard.
    """
    ig_section = f"""
        <p><strong>Instagram Account ID:</strong></p>
        <div style="background:#f5f5f5; padding:12px; border-radius:4px; word-break:break-all; font-family:monospace;">
            {ig_account_id}
        </div>
    """ if ig_account_id else "<p style='color:#e65100;'>No Instagram Business Account found linked to your Facebook Page. Contact Brandon.</p>"

    return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 20px;">
            <h2 style="color: #2e7d32;">You're all set!</h2>
            <p>Your Instagram account has been connected successfully.</p>
            <p><strong>Token expires in:</strong> ~{days} days</p>
            <p>You can close this window. Brandon will take it from here.</p>
            <hr>
            <p style="color:#888; font-size:12px;">
                For Brandon — token and account ID saved to database automatically.
            </p>
            {ig_section}
            <p style="font-size:12px; color:#888;"><strong>Access Token:</strong></p>
            <div style="background:#f5f5f5; padding:12px; border-radius:4px; word-break:break-all; font-size:11px; font-family:monospace; color:#333;">
                {access_token}
            </div>
        </body>
        </html>
    """


if __name__ == "__main__":
    if not APP_ID or not APP_SECRET:
        raise EnvironmentError(
            "INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET must be set."
        )
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Auth server starting on port {port}")
    logger.info(f"Auth flow: {AUTH_FLOW.upper()}")
    logger.info(f"Redirect URI: {REDIRECT_URI}")
    app.run(host="0.0.0.0", port=port, debug=False)