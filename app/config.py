import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Used only in debug mode and in tests, so sessions and CSRF work without a .env.
DEV_SECRET_KEY = "dev-only-not-secret"


def _env_flag(name: str, default: str) -> bool:
    """'true' / 'false' from an environment variable."""
    return os.environ.get(name, default).lower() == "true"


def _env_list(name: str) -> list[str] | None:
    """A comma-separated list ("a.com, b.com"); None when the variable is empty."""
    items = [item.strip() for item in os.environ.get(name, "").split(",")]
    return [item for item in items if item] or None


def with_psycopg_driver(url: str | None) -> str | None:
    """Neon gives 'postgresql://...' URLs. SQLAlchemy would then look for psycopg2,
    but we install psycopg 3, so the driver is named in the URL."""
    if url and url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


class Config:
    """Reads all settings from environment variables (.env in development)."""

    SECRET_KEY = os.environ.get("SECRET_KEY")  # required in production
    SQLALCHEMY_DATABASE_URI = with_psycopg_driver(os.environ.get("DATABASE_URL"))
    # Neon closes idle connections; test each one before use instead of failing.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Absolute URLs (sitemap, Stripe return URLs) are built from the Host header,
    # so in production only our own domain is accepted (other hosts get 400).
    TRUSTED_HOSTS = _env_list("TRUSTED_HOSTS")

    RATELIMIT_ENABLED = True

    SESSION_COOKIE_HTTPONLY = True   # JavaScript cannot read the session cookie
    SESSION_COOKIE_SAMESITE = "Lax"  # cookie is not sent on cross-site POSTs
    # Only sent over HTTPS; on in production, off locally (http://localhost).
    SESSION_COOKIE_SECURE = _env_flag("SESSION_COOKIE_SECURE", "false")

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # Flask rejects bigger requests with 413
    # Outside static/, so the web server never serves it directly.
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "private_uploads"))

    # The activity log (one line per request and per important action).
    ACTIVITY_LOG = os.environ.get("ACTIVITY_LOG", str(BASE_DIR / "logs" / "activity.log"))

    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")

    CAPTCHA_ENABLED = _env_flag("CAPTCHA_ENABLED", "true")
    RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY")
    RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY")


def check_required_settings(app) -> None:
    """Refuse to start in production without the secrets (no unsafe defaults in code).
    In debug mode and in tests a fixed development SECRET_KEY is enough."""
    if app.debug or app.testing:
        app.config["SECRET_KEY"] = app.config["SECRET_KEY"] or DEV_SECRET_KEY
        return

    required = ["SECRET_KEY"]
    if app.config["CAPTCHA_ENABLED"]:
        required += ["RECAPTCHA_SITE_KEY", "RECAPTCHA_SECRET_KEY"]
    missing = [name for name in required if not app.config.get(name)]
    if missing:
        raise RuntimeError(f"Missing settings: {', '.join(missing)} (set them as environment variables)")
