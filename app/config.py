import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Reads all settings from environment variables (.env in development)."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    SESSION_COOKIE_HTTPONLY = True   # JavaScript cannot read the session cookie
    SESSION_COOKIE_SAMESITE = "Lax"  # cookie is not sent on cross-site POSTs