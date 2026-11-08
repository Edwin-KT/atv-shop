import os
import tempfile
from pathlib import Path

# Set BEFORE anything imports the app (fake_gateway does too): app.config reads it at
# import time, so tests that call create_app() themselves never write to logs/.
os.environ.setdefault("ACTIVITY_LOG", str(Path(tempfile.gettempdir()) / "atv-shop-tests.log"))

import pytest  # noqa: E402
from fake_gateway import FakeGateway  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import limiter  # noqa: E402


def build_app(tmp_path, rate_limit: bool = False, captcha: bool = False):
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "UPLOAD_FOLDER": str(tmp_path / "private_uploads"),
            "ACTIVITY_LOG": str(tmp_path / "activity.log"),
            "PAYMENT_GATEWAY": FakeGateway(),
            "RATELIMIT_ENABLED": rate_limit,
            "CAPTCHA_ENABLED": captcha,
        }
    )


@pytest.fixture()
def app(tmp_path):
    return build_app(tmp_path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def limited_app(tmp_path):
    """Same app, but with rate limiting switched ON."""
    app = build_app(tmp_path, rate_limit=True)
    limiter.reset()  # counters are global: start every limiter test from zero
    return app


class FakeGoogleAnswer:
    def __init__(self, success):
        self.success = success

    def raise_for_status(self):
        pass

    def json(self):
        return {"success": self.success}


@pytest.fixture()
def google_calls(monkeypatch):
    """Replaces the call to Google: only the token "valid-token" is accepted.
    Returns the list of tokens the app sent, so a test can check them."""
    calls = []

    def fake_post(url, data, timeout):
        calls.append(data["response"])
        return FakeGoogleAnswer(data["response"] == "valid-token")

    monkeypatch.setattr("app.services.captcha.requests.post", fake_post)
    return calls


@pytest.fixture()
def captcha_app(tmp_path, google_calls):
    """Same app, but with the CAPTCHA switched ON (Google is faked, see google_calls)."""
    return build_app(tmp_path, captcha=True)


@pytest.fixture()
def log_text(tmp_path):
    """A function that returns everything written to the activity log during the test."""

    def read():
        log_file = tmp_path / "activity.log"
        return log_file.read_text(encoding="utf-8") if log_file.exists() else ""

    return read
