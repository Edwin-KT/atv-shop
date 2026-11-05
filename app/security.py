from functools import wraps

from flask import abort, request
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


def _has_nul(text) -> bool:
    return isinstance(text, str) and "\x00" in text


def reject_nul_bytes():
    """before_request: answer 400 if any parameter contains a NUL byte.

    PostgreSQL text fields cannot store NUL, so such a value would crash the
    first query that uses it (500). Checked once here for every route: path
    parameters, query string, form fields and uploaded file names."""
    values = list((request.view_args or {}).values())
    for params in (request.args, request.form):
        for key, value in params.items(multi=True):
            values += [key, value]
    values += [upload.filename for upload in request.files.values()]

    if any(_has_nul(value) for value in values):
        abort(400)
