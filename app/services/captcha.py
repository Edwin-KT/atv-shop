import requests
from flask import current_app, request

from app.services.audit import record_event

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
FORM_FIELD = "g-recaptcha-response"
MAX_TOKEN_LENGTH = 4096


class RecaptchaVerifier:
    """Asks Google whether a CAPTCHA token is valid."""

    def __init__(self, secret_key: str | None, timeout: float = 5.0):
        self._secret_key = secret_key
        self._timeout = timeout

    def verify(self, token: str, remote_ip: str | None = None) -> bool:
        """True only when Google confirms the token. Any problem means False
        (fail closed): missing token, no secret key, network error, bad answer."""
        if not token or len(token) > MAX_TOKEN_LENGTH or not self._secret_key:
            return False
        try:
            response = requests.post(
                VERIFY_URL,
                data={"secret": self._secret_key, "response": token, "remoteip": remote_ip},
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json().get("success") is True
        except (requests.RequestException, ValueError):
            return False


def captcha_passed() -> bool:
    """Check the CAPTCHA of the current form submission and audit failures."""
    if not current_app.config["CAPTCHA_ENABLED"]:
        return True

    verifier = current_app.extensions["captcha_verifier"]
    passed = verifier.verify(request.form.get(FORM_FIELD, ""), request.remote_addr)
    if not passed:
        record_event("captcha_failed", details=f"path={request.path}")
    return passed