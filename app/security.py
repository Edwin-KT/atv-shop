from functools import wraps

from flask import abort
from flask_login import current_user

from app.extensions import login_manager


def check_admin_access():
    """Return a redirect for anonymous users, abort(403) for non-admins,
    or None when the current user is an admin."""
    if not current_user.is_authenticated:
        return login_manager.unauthorized()
    if not current_user.is_admin:
        abort(403)
    return None


def admin_required(view):
    """Decorator version, for single routes outside the admin blueprint."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        denied = check_admin_access()
        if denied is not None:
            return denied
        return view(*args, **kwargs)

    return wrapped