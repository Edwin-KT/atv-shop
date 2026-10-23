from app.extensions import db
from app.models import User
from app.models.user import ROLE_ADMIN
from app.validators import is_valid_email, is_valid_password, is_valid_phone


def create_admin(email: str, phone: str, password: str) -> User:
    """Create an admin account. Raises ValueError with a readable message."""
    email = email.strip().lower()

    if not is_valid_email(email):
        raise ValueError("Invalid email address.")
    if not is_valid_phone(phone):
        raise ValueError("Phone number must have exactly 10 digits.")
    if not is_valid_password(password):
        raise ValueError("Password must have at least 8 characters.")
    if User.query.filter_by(email=email).first():
        raise ValueError("An account with this email already exists.")

    admin = User(email=email, phone=phone, role=ROLE_ADMIN)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return admin