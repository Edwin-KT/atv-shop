from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

# Rate limit: after 100 requests in one minute from the same IP, the next ones get
# 429 Too Many Requests until the minute is over. Counters live in memory, so the
# app must run as ONE process (gunicorn -w 1).
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per minute"],
    storage_uri="memory://",
    headers_enabled=True,  # sends Retry-After and X-RateLimit-* headers
)


@limiter.request_filter
def exempt_static_files():
    """One page loads several CSS, JS and image files; they must not use up the limit."""
    return request.endpoint == "static"