"""reCAPTCHA v2 on the register and login forms, checked on the server.

The widget in the browser puts a token in the form field "g-recaptcha-response".
The server sends that token to Google and only continues when Google says it is
valid. Any problem counts as "not passed" (fail closed): no token, no secret key,
Google unreachable or an unexpected answer."""

import requests
from flask import current_app, request

from app.activity_log import log_event

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


def captcha_passed() -> bool:
    """Check the CAPTCHA of the form that was just submitted; log failures."""
    if not current_app.config["CAPTCHA_ENABLED"]:  # switched off in most tests
        return True

    if ask_google(request.form.get("g-recaptcha-response", "")):
        return True
    log_event("captcha_failed", details=f"path={request.path}")
    return False


def ask_google(token: str) -> bool:
    """True only when Google confirms the token."""
    secret_key = current_app.config["RECAPTCHA_SECRET_KEY"]
    # Real tokens are a few hundred characters; anything empty or huge is not sent.
    if not token or len(token) > 4096 or not secret_key:
        return False
    try:
        response = requests.post(
            VERIFY_URL,
            data={"secret": secret_key, "response": token, "remoteip": request.remote_addr},
            timeout=5,  # never let a slow Google block the login page for long
        )
        response.raise_for_status()  # an HTTP error status (e.g. 500) counts as failed
        return response.json().get("success") is True
    except (requests.RequestException, ValueError):  # network error, or not JSON
        return False
