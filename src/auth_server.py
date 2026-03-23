"""
OAuth Callback Handler
----------------------
A lightweight Flask app that handles the Instagram OAuth flow.

How it works:
  1. You call InstagramClient.build_auth_url() to generate an authorization URL
  2. Anthony visits that URL and approves your app on Instagram
  3. Instagram redirects Anthony's browser to YOUR redirect_uri with a short-lived code
  4. This Flask app catches that redirect, exchanges the code for a long-lived token,
     and saves it to your .env file automatically

Setup:
  1. Install Flask:          pip install flask
  2. Set redirect URI in Meta App Dashboard to: http://localhost:8000/callback
  3. Run this server:        python src/auth_server.py
  4. Generate the auth URL:  python src/generate_auth_url.py
  5. Send Anthony the URL — after he approves, the token is saved automatically

NOTE: For production, this server needs to be hosted at a public URL (not localhost).
Options: ngrok (free, for testing), Railway, Render, or any basic VPS.
For the test phase with Anthony, ngrok is the simplest option.
"""

import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv, set_key
from instagram_client import InstagramClient, InstagramAPIError

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

APP_ID       = os.getenv("INSTAGRAM_APP_ID")
APP_SECRET   = os.getenv("INSTAGRAM_APP_SECRET")
REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/callback")
ENV_FILE     = os.path.join(os.path.dirname(__file__), "../.env")


@app.route("/")
def index():
    """Health check — confirms the server is running."""
    return jsonify({"status": "Auth server is running. Waiting for OAuth callback."})


@app.route("/callback")
def callback():
    """
    Instagram redirects here after the user approves (or denies) your app.
    URL will look like: http://localhost:8000/callback?code=XXXXX
    or on denial:       http://localhost:8000/callback?error=access_denied
    """
    # -- Handle user denial --
    error = request.args.get("error")
    if error:
        reason = request.args.get("error_reason", "unknown")
        logger.error(f"User denied authorization. Reason: {reason}")
        return f"""
            <h2>Authorization Denied</h2>
            <p>The Instagram account owner denied access. Reason: {reason}</p>
            <p>Please try again or contact the account owner.</p>
        """, 400

    # -- Extract the short-lived code --
    code = request.args.get("code")
    if not code:
        logger.error("No code received in callback.")
        return "<h2>Error</h2><p>No authorization code received.</p>", 400

    logger.info("Authorization code received. Exchanging for long-lived token...")

    # -- Exchange short-lived code for long-lived token --
    try:
        token_data = InstagramClient.exchange_short_lived_token(
            app_id=APP_ID,
            app_secret=APP_SECRET,
            short_lived_token=code,
        )
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return f"<h2>Token Exchange Failed</h2><p>{e}</p>", 500

    access_token = token_data.get("access_token")
    expires_in   = token_data.get("expires_in", 0)
    days         = round(expires_in / 86400)

    if not access_token:
        return "<h2>Error</h2><p>No access token in response.</p>", 500

    # -- Save token to .env automatically --
    try:
        set_key(ENV_FILE, "INSTAGRAM_ACCESS_TOKEN", access_token)
        logger.info(f"Access token saved to .env. Expires in ~{days} days.")
    except Exception as e:
        logger.warning(f"Could not auto-save token to .env: {e}")
        logger.info(f"Manual save needed. Token: {access_token}")

    logger.info("OAuth flow complete. You can now run the pull job.")

    return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 20px;">
            <h2 style="color: #2e7d32;">Authorization Successful</h2>
            <p>The Instagram account has been connected successfully.</p>
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
    logger.info(f"Redirect URI: {REDIRECT_URI}")
    app.run(host="0.0.0.0", port=8000, debug=False)