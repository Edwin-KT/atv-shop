"""INTEGRATION tests: register, login and logout through the real routes.

Rubric: N3.03 authentication (hashed passwords, login, logout, safe redirect after
login); the server checks the email and the phone (exactly 10 digits); N2.02 use
case "account"."""

import re

import pytest

from app.extensions import db
from app.models import User
from helpers import PASSWORD, seed

REGISTER = {"email": "ana@gmail.com", "phone": "0712345678", "password": PASSWORD}
LOGIN = {"email": "ana@gmail.com", "password": PASSWORD}


def user_count(app):
    with app.app_context():
        return User.query.count()


@pytest.fixture()
def customer(app):
    """An existing customer account (not logged in yet)."""
    with app.app_context():
        user = User(email=LOGIN["email"], phone="0712345678")
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()


# --- register ---


def test_register_creates_a_customer_with_a_hashed_password(app, client):
    response = client.post("/register", data={**REGISTER, "role": "admin"})  # the client tries to pick a role

    assert response.status_code == 302
    with app.app_context():
        user = User.query.one()
        assert user.password_hash != PASSWORD  # only a salted hash is stored
        assert user.check_password(PASSWORD)
        assert user.role == "customer"  # the role is never read from the form


def test_register_rejects_a_phone_without_exactly_10_digits(app, client):
    response = client.post("/register", data={**REGISTER, "phone": "123"})

    assert response.status_code == 400
    assert b"Phone number must have exactly 10 digits." in response.data
    assert user_count(app) == 0


def test_register_rejects_an_invalid_email(app, client):
    response = client.post("/register", data={**REGISTER, "email": "not-an-email"})

    assert response.status_code == 400
    assert user_count(app) == 0


def test_register_rejects_a_duplicate_email(app, client):
    client.post("/register", data=REGISTER)

    response = client.post("/register", data=REGISTER)

    assert response.status_code == 400
    assert user_count(app) == 1


# --- login and logout ---


def test_login_with_the_right_password(customer, client):
    response = client.post("/login", data=LOGIN)

    assert response.status_code == 302
    assert b"Logout" in client.get("/").data


@pytest.mark.parametrize(
    "data",
    [{**LOGIN, "password": "gresita-123"}, {**LOGIN, "email": "nobody@gmail.com"}],
    ids=["wrong password", "unknown email"],
)
def test_login_fails_with_the_same_message(customer, client, data):
    """The same answer for both cases: an attacker cannot learn which emails exist."""
    response = client.post("/login", data=data)

    assert response.status_code == 401
    assert b"Invalid email or password." in response.data
    assert b"Logout" not in client.get("/").data


def test_logout_needs_a_post_and_ends_the_session(customer, client):
    client.post("/login", data=LOGIN)

    assert client.get("/logout").status_code == 405  # a link cannot log you out
    client.post("/logout")

    assert b"Logout" not in client.get("/").data


# --- where the customer goes after logging in (?next=...) ---


def test_login_with_next_goes_back_to_that_page(customer, client):
    response = client.post("/login?next=/cart", data=LOGIN)

    assert response.headers["Location"] == "/cart"


@pytest.mark.parametrize("target", ["https://evil.com", "//evil.com", r"/\evil.com"])
def test_login_never_redirects_to_another_site(customer, client, target):
    """No open redirect: a link to our login page cannot send people to a phishing site."""
    response = client.post("/login", query_string={"next": target}, data=LOGIN)

    assert response.headers["Location"] == "/"


def test_a_guest_who_clicks_log_in_to_pay_comes_back_to_the_cart(app, customer, client):
    seed(app)
    client.post("/cart/add/1", data={"quantity": 1})

    cart = client.get("/cart").get_data(as_text=True)
    login_link = re.search(r'href="(/login\?next=[^"]+)">Log in to pay</a>', cart).group(1)

    assert client.post(login_link, data=LOGIN).headers["Location"] == "/cart"
