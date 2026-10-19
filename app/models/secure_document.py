from datetime import datetime, timezone

from app.extensions import db


class SecureDocument(db.Model):
    """Metadata about an uploaded PDF. The file itself lives in private_uploads/."""

    __tablename__ = "secure_documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)  # for display only
    stored_filename = db.Column(db.String(64), unique=True, nullable=False)  # uuid on disk
    size_bytes = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )