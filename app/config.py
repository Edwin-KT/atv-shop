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

    SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:5000").rstrip("/")
    SITE_NAME = "ATV & Enduro Shop"

    SESSION_COOKIE_HTTPONLY = True   # JavaScript cannot read the session cookie
    SESSION_COOKIE_SAMESITE = "Lax"  # cookie is not sent on cross-site POSTs

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # Flask rejects bigger requests with 413
    # Outside static/, so the web server never serves it directly.
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "private_uploads"))

    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
    
    CAPTCHA_ENABLED = os.environ.get("CAPTCHA_ENABLED", "true").lower() == "true"
    RECAPTCHA_SITE_KEY = os.environ.get(
        "RECAPTCHA_SITE_KEY", "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
    )
    RECAPTCHA_SECRET_KEY = os.environ.get(
        "RECAPTCHA_SECRET_KEY", "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
    )