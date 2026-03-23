<<<<<<< HEAD
# Instagram Graph API — Engagement Data Pipeline

A Python project that connects to the Instagram Graph API to pull likes and comments data, store daily engagement snapshots, and lay the groundwork for a dashboard layer.

Built as a demonstration of API integration, OAuth token management, rate limit handling, and structured data storage.

---

## Features

- **OAuth 2.0 authentication** — short-lived to long-lived token exchange, plus proactive token refresh before expiry
- **Rate limit handling** — exponential backoff on API rate limit errors (codes 4, 17, 32, 613) so the app never crashes silently
- **Daily engagement snapshots** — idempotent daily pulls with duplicate protection at the database level
- **Comment ingestion** — stores all comments per media post with user and timestamp data
- **Mock client** — full pipeline runs without real credentials for demos and development
- **Unit tested** — pytest suite covering client behavior and database operations

---

## Project Structure

```
instagram-api-demo/
├── src/
│   ├── instagram_client.py   # API client — auth, requests, rate limiting
│   ├── database.py           # SQLite storage layer
│   ├── pull_job.py           # Daily pull job entry point
│   └── mock_client.py        # Mock client for demos and testing
├── tests/
│   └── test_instagram.py     # Unit tests (pytest)
├── demo.py                   # Run the full pipeline with mock data
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the demo (no credentials needed)

```bash
python demo.py
```

This runs the full pipeline — profile check, media pull, comment ingestion, daily snapshot, trend query — using mock data.

### 3. Run unit tests

```bash
pytest tests/
```

---

## Production Setup

### Prerequisites

- A **Meta Developer App** at [developers.facebook.com](https://developers.facebook.com)
- An **Instagram Business or Creator account** linked to a Facebook Page
- Your account added as a test user in the Meta App dashboard

### Configure credentials

```bash
cp .env.example .env
# Fill in INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET
```

### Run the live pull job

```bash
python src/pull_job.py
```

### Schedule daily pulls (cron example)

```cron
0 8 * * * /usr/bin/python3 /path/to/src/pull_job.py >> /var/log/instagram_pull.log 2>&1
```

---

## Token Management

Instagram long-lived tokens expire after **60 days**. The client warns proactively when a token is within 5 days of expiry. To refresh:

```python
from src.instagram_client import InstagramClient
client = InstagramClient(access_token="your_token")
client.refresh_long_lived_token(app_secret="your_app_secret")
```

For production, automate this on a ~50-day schedule so the app never goes down due to token expiry.

---

## Rate Limits

The Instagram Graph API uses a dynamic rate limit based on the number of users connected to your app. The client handles limits gracefully:

- Detects rate limit error codes: `4`, `17`, `32`, `613`, `80001`, `80006`
- Backs off with exponential delay: `2s → 4s → 8s → 16s`
- Logs each retry so you can monitor patterns
- If all retries fail, raises `InstagramAPIError` for upstream handling

---

## Architecture Overview

```
Scheduler (cron / APScheduler)
        │
        ▼
   pull_job.py
        │
        ├──▶ InstagramClient  ──▶  Instagram Graph API
        │         │
        │    Rate limit handling
        │    Token refresh logic
        │
        └──▶ database.py  ──▶  SQLite (swappable for PostgreSQL)
                  │
                  ├── media table
                  ├── comments table
                  └── daily_snapshots table
                            │
                            ▼
                    Dashboard layer
                  (reads from DB, not live API)
```

The dashboard reads from the database rather than hitting the API directly — this keeps API calls predictable, avoids rate limits during peak usage, and makes the dashboard fast.

---

## Stack

- **Python 3.9+**
- `requests` — HTTP client
- `python-dotenv` — environment variable management
- `sqlite3` — built-in, no extra install needed
- `pytest` — unit testing
=======
# instagram-graph-api-demo
Demoing using the instagram Graph API
>>>>>>> ea59bee8b8ed879dcde5e2314676f1722526ca2a
