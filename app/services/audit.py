from flask import current_app, request


def record_event(event_type: str, user_id: int | None = None, details: str | None = None):
    """Record a security/business event."""
    current_app.logger.info(
        "event=%s user_id=%s ip=%s details=%s",
        event_type,
        user_id,
        request.remote_addr,
        details,
    )