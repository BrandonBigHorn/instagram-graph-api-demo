"""
Generate Auth URL
-----------------
Prints the OAuth authorization URL to send to the Instagram account owner.
They visit this URL, log in, and approve your app.
After approval, Instagram redirects them to your callback URL
and the auth_server.py catches the token automatically.

Run with: python src/generate_auth_url.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from instagram_client import InstagramClient

load_dotenv()

APP_ID       = os.getenv("INSTAGRAM_APP_ID")
REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/callback")

if not APP_ID:
    raise EnvironmentError("INSTAGRAM_APP_ID not set in .env file.")

url = InstagramClient.build_auth_url(app_id=APP_ID, redirect_uri=REDIRECT_URI)

print("\n" + "=" * 60)
print("  Instagram Authorization URL")
print("=" * 60)
print(f"\n{url}\n")
print("Steps:")
print("  1. Make sure auth_server.py is running (python src/auth_server.py)")
print("  2. Send this URL to the Instagram account owner")
print("  3. They log in and click Approve")
print("  4. The token is saved to your .env automatically")
print("=" * 60 + "\n")