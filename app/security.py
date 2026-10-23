from functools import wraps

from flask import abort
from flask_login import current_user

from app.extensions import login_manager


def admin_required(view):
    """Allow only logged-in admins: anonymous -> login page, customer -> 403."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped