import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Reads all settings from environment variables (.env in development)."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    RATELIMIT_ENABLED = True

    SESSION_COOKIE_HTTPONLY = True   # JavaScript cannot read the session cookie
    SESSION_COOKIE_SAMESITE = "Lax"  # cookie is not sent on cross-site POSTs

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # Flask rejects bigger requests with 413
    # Outside static/, so the web server never serves it directly.
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "private_uploads"))

    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")