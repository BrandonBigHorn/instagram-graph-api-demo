"""
Generate Auth URL
-----------------
Generates the correct OAuth URL based on AUTH_FLOW in your .env file.

  AUTH_FLOW=instagram  -> Instagram Login URL
  AUTH_FLOW=facebook   -> Facebook Login URL

Run with: python src/generate_auth_url.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from instagram_client import InstagramClient
from facebook_client import FacebookLoginClient

load_dotenv()

APP_ID       = os.getenv("INSTAGRAM_APP_ID")
REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/callback")
AUTH_FLOW    = os.getenv("AUTH_FLOW", "instagram").lower()

if not APP_ID:
    raise EnvironmentError("INSTAGRAM_APP_ID not set in .env file.")

if AUTH_FLOW == "facebook":
    url = FacebookLoginClient.build_auth_url(app_id=APP_ID, redirect_uri=REDIRECT_URI)
    flow_label = "Facebook Login (for accounts linked to a Facebook Page)"
else:
    url = InstagramClient.build_auth_url(app_id=APP_ID, redirect_uri=REDIRECT_URI)
    flow_label = "Instagram Login"

print("\n" + "=" * 60)
print(f"  Instagram Authorization URL")
print(f"  Flow: {flow_label}")
print("=" * 60)
print(f"\n{url}\n")
print("Steps:")
print("  1. Make sure auth_server.py is running (python src/auth_server.py)")
print("  2. Send this URL to the Instagram account owner")
print("  3. They log in and click Approve")
print("  4. The token is saved to your .env automatically")
print("=" * 60 + "\n")