"""INTEGRATION tests: the CAPTCHA on the register and login forms, through the app
(Google is replaced by the google_calls fixture in conftest.py).

Rubric: N10.02 CAPTCHA (no account and no login without a valid token; the CAPTCHA
is checked before the password); N3.03 authentication."""

from app.extensions import db
from app.models import User

PASSWORD = "parola-sigura-123"
REGISTER = {"email": "ana@gmail.com", "phone": "0712345678", "password": PASSWORD}
LOGIN = {"email": "ana@gmail.com", "password": PASSWORD}


def create_user(app):
    with app.app_context():
        user = User(email=LOGIN["email"], phone="0712345678")
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()


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


def test_captcha_is_checked_before_the_password(captcha_app, log_text):
    """A bot with a wrong CAPTCHA learns nothing about passwords: no login_failed event."""
    create_user(captcha_app)

    captcha_app.test_client().post("/login", data={**LOGIN, "password": "gresita-123"})

    assert "event=login_failed" not in log_text()
    assert "event=captcha_failed" in log_text()


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


def test_nothing_is_checked_when_captcha_is_disabled(client):
    response = client.post("/register", data=REGISTER)

    assert response.status_code == 302
    assert b"recaptcha" not in client.get("/login").data


def test_get_requests_do_not_ask_google(captcha_app, google_calls):
    captcha_app.test_client().get("/login")

    assert google_calls == []


def test_the_submitted_token_is_what_google_checks(captcha_app, google_calls):
    captcha_app.test_client().post("/login", data={**LOGIN, "g-recaptcha-response": "valid-token"})

    assert google_calls == ["valid-token"]