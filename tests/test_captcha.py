import pytest
import requests

from app.extensions import db
from app.models import AuditLog, User
from app.services.captcha import VERIFY_URL, RecaptchaVerifier

PASSWORD = "parola-sigura-123"
REGISTER = {"email": "ana@gmail.com", "phone": "0712345678", "password": PASSWORD}
LOGIN = {"email": "ana@gmail.com", "password": PASSWORD}


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self._payload = payload if payload is not None else {}
        self._status = status

    def raise_for_status(self):
        if self._status >= 400:
            raise requests.HTTPError("bad status")

    def json(self):
        return self._payload


def create_user(app):
    with app.app_context():
        user = User(email=LOGIN["email"], phone="0712345678")
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()


def event_types(app):
    with app.app_context():
        return [e.event_type for e in AuditLog.query.order_by(AuditLog.id)]


# --- the verifier (unit tests, network mocked) ---

def test_verifier_accepts_token_confirmed_by_google(monkeypatch):
    captured = {}

    def fake_post(url, data, timeout):
        captured.update(url=url, data=data, timeout=timeout)
        return FakeResponse({"success": True})

    monkeypatch.setattr(requests, "post", fake_post)

    assert RecaptchaVerifier("secret").verify("token-1", "1.2.3.4") is True
    assert captured["url"] == VERIFY_URL
    assert captured["data"] == {"secret": "secret", "response": "token-1", "remoteip": "1.2.3.4"}
    assert captured["timeout"] > 0


def test_verifier_rejects_token_refused_by_google(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"success": False}))

    assert RecaptchaVerifier("secret").verify("token-1") is False


def test_verifier_fails_closed_on_network_error(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests, "post", boom)

    assert RecaptchaVerifier("secret").verify("token-1") is False


def test_verifier_fails_closed_on_bad_answer(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse(status=500))
    assert RecaptchaVerifier("secret").verify("token-1") is False

    class NotJson(FakeResponse):
        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(requests, "post", lambda *a, **k: NotJson())
    assert RecaptchaVerifier("secret").verify("token-1") is False


@pytest.mark.parametrize("token", ["", None, "x" * 5000])
def test_verifier_does_not_call_google_for_unusable_tokens(monkeypatch, token):
    def must_not_run(*args, **kwargs):
        raise AssertionError("network call made")

    monkeypatch.setattr(requests, "post", must_not_run)

    assert RecaptchaVerifier("secret").verify(token) is False


def test_verifier_without_secret_key_rejects_everything(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"success": True}))

    assert RecaptchaVerifier(None).verify("token-1") is False


# --- registration ---

def test_register_without_captcha_is_rejected(captcha_app):
    response = captcha_app.test_client().post("/register", data=REGISTER)

    assert response.status_code == 400
    assert b"not a robot" in response.data
    with captcha_app.app_context():
        assert User.query.count() == 0


def test_register_with_invalid_captcha_is_rejected(captcha_app):
    response = captcha_app.test_client().post(
        "/register", data={**REGISTER, "g-recaptcha-response": "forged"}
    )

    assert response.status_code == 400
    with captcha_app.app_context():
        assert User.query.count() == 0


def test_register_with_valid_captcha_works(captcha_app):
    response = captcha_app.test_client().post(
        "/register", data={**REGISTER, "g-recaptcha-response": "valid-token"}
    )

    assert response.status_code == 302
    with captcha_app.app_context():
        assert User.query.count() == 1


# --- login ---

def test_login_without_captcha_is_rejected_even_with_correct_password(captcha_app):
    create_user(captcha_app)
    client = captcha_app.test_client()

    response = client.post("/login", data=LOGIN)

    assert response.status_code == 400
    assert b"Logout" not in client.get("/").data


def test_login_with_valid_captcha_works(captcha_app):
    create_user(captcha_app)
    client = captcha_app.test_client()

    response = client.post("/login", data={**LOGIN, "g-recaptcha-response": "valid-token"})

    assert response.status_code == 302
    assert b"Logout" in client.get("/").data


def test_captcha_is_checked_before_the_password(captcha_app):
    """A bot with a wrong CAPTCHA learns nothing about passwords: no login_failed event."""
    create_user(captcha_app)

    captcha_app.test_client().post("/login", data={**LOGIN, "password": "gresita-123"})

    assert "login_failed" not in event_types(captcha_app)
    assert "captcha_failed" in event_types(captcha_app)


def test_wrong_password_with_valid_captcha_is_still_rejected(captcha_app):
    create_user(captcha_app)

    response = captcha_app.test_client().post(
        "/login", data={**LOGIN, "password": "gresita-123", "g-recaptcha-response": "valid-token"}
    )

    assert response.status_code == 401


# --- widget and configuration ---

def test_widget_is_shown_on_login_and_register(captcha_app):
    client = captcha_app.test_client()

    for url in ("/login", "/register"):
        html = client.get(url).get_data(as_text=True)
        assert 'class="g-recaptcha"' in html
        assert "data-sitekey=" in html
        assert "recaptcha/api.js" in html


def test_widget_is_not_on_other_pages(captcha_app):
    assert b"recaptcha" not in captcha_app.test_client().get("/").data


def test_nothing_is_checked_when_captcha_is_disabled(client):
    response = client.post("/register", data=REGISTER)

    assert response.status_code == 302
    assert b"recaptcha" not in client.get("/login").data


def test_get_requests_do_not_call_the_verifier(captcha_app):
    captcha_app.test_client().get("/login")

    assert captcha_app.extensions["captcha_verifier"].calls == []