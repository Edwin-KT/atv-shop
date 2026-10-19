from flask import current_app, request

from app.extensions import db
from app.models import AuditLog


def record_event(event_type: str, user_id: int | None = None, details: str | None = None):
    """Record a security/business event in the log file AND in the audit_logs table."""
    current_app.logger.info(
        "event=%s user_id=%s ip=%s details=%s",
        event_type,
        user_id,
        request.remote_addr,
        details,
    )

    entry = AuditLog(
        event_type=event_type,
        user_id=user_id,
        ip_address=request.remote_addr,
        details=details[:500] if details else None,
    )
    db.session.add(entry)
    db.session.commit()