import pytest
from fake_captcha import FakeCaptcha
from fake_gateway import FakeGateway

from app import create_app
from app.extensions import limiter


def build_app(tmp_path, rate_limit: bool = False, captcha: bool = False):
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "UPLOAD_FOLDER": str(tmp_path / "private_uploads"),
            "PAYMENT_GATEWAY": FakeGateway(),
            "RATELIMIT_ENABLED": rate_limit,
            "CAPTCHA_ENABLED": captcha,
            "CAPTCHA_VERIFIER": FakeCaptcha(),
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


@pytest.fixture()
def captcha_app(tmp_path):
    """Same app, but with the CAPTCHA switched ON (and a fake verifier)."""
    return build_app(tmp_path, captcha=True)