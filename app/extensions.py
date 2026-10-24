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

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per minute"],  # the requirement: max 100 requests / minute
    storage_uri="memory://",
    headers_enabled=True,  # sends Retry-After and X-RateLimit-* headers
)


@limiter.request_filter
def exempt_static_and_health():
    return request.endpoint in ("static", "health")