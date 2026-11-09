"""Activity log: what users do on the site, written to one text file.

Two kinds of lines go to logs/activity.log:
- one line for every request (who, from which IP, which page, which status);
- one line for every important action, written with log_event() ("login_failed",
  "order_paid", "document_uploaded", ...).
Admins read the newest lines at /admin/log. Passwords, form fields and query
strings are never logged."""

import logging
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import current_app, request
from flask_login import current_user

logger = logging.getLogger("shop.activity")
ADMIN_LOG_LINES = 100  # how many of the newest lines /admin/log shows


def setup_activity_log(app):
    """Send the log to the file named in ACTIVITY_LOG and log every request."""
    log_file = Path(app.config["ACTIVITY_LOG"])
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # The logger is shared by every app object (the tests create many), so the
    # old file handler is closed and replaced by one for this app's file.
    for old in list(logger.handlers):
        old.close()
        logger.removeHandler(old)
    # The file is rotated at about 1 MB; the 5 previous files are kept.
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    @app.after_request
    def log_request(response):
        if request.endpoint != "static":  # CSS, JS and images would only add noise
            # Only the path: the query string can hold secrets (e.g. Stripe's session id).
            # !r writes a newline as "\n", so nobody can forge extra log lines.
            logger.info(
                "ip=%s user=%s %s %r status=%s",
                request.remote_addr,
                _user_id(),
                request.method,
                request.path[:200],
                response.status_code,
            )
        return response


def log_event(event: str, user_id: int | None = None, details: str = ""):
    """Write one important action, e.g. log_event("order_paid", details="order_id=3")."""
    if user_id is None:
        user_id = _user_id()
    message = f"ip={request.remote_addr} user={user_id} event={event}"
    if details:  # no trailing space when there is nothing to add
        message += " " + details[:300]
    logger.info(message)


def read_last_lines(count: int = ADMIN_LOG_LINES) -> list[str]:
    """The newest `count` lines of the log, newest first (for /admin/log)."""
    log_file = Path(current_app.config["ACTIVITY_LOG"])
    if not log_file.exists():
        return []
    with log_file.open(encoding="utf-8") as file:
        last = deque(file, maxlen=count)  # keeps only the last lines in memory
    return [line.rstrip("\n") for line in reversed(last)]


def _user_id():
    return current_user.id if current_user.is_authenticated else "-"
