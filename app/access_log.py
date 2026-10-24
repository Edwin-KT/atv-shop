import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import g, request
from flask_login import current_user

ACCESS_LOGGER_NAME = "shop.access"


def configure_access_log(app):
    """Log every request (method, path, status, user, IP, duration).

    Only the path is logged: never the query string or the form data,
    because those can contain passwords, CSRF tokens or payment session ids."""
    logger = logging.getLogger(ACCESS_LOGGER_NAME)
    logger.setLevel(logging.INFO)

    if not app.config.get("TESTING") and not logger.handlers:
        log_dir = Path(app.root_path).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "access.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)

    @app.before_request
    def start_timer():
        g.request_started = time.perf_counter()

    @app.after_request
    def log_request(response):
        if request.endpoint == "static":
            return response

        started = getattr(g, "request_started", None)
        duration_ms = int((time.perf_counter() - started) * 1000) if started else -1
        user_id = current_user.id if current_user.is_authenticated else "-"

        logger.info(
            "ip=%s user=%s method=%s path=%r status=%s duration_ms=%s",
            request.remote_addr,
            user_id,
            request.method,
            request.path[:200],
            response.status_code,
            duration_ms,
        )
        return response