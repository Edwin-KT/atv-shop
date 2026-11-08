import re

import pytest

from app.extensions import db
from app.models import User
from app.seed import seed_products

CREDENTIALS = {"email": "ana@gmail.com", "password": "parola-sigura-123"}


def create_user(app):
    with app.app_context():
        user = User(email=CREDENTIALS["email"], phone="0712345678")
        user.set_password(CREDENTIALS["password"])
        db.session.add(user)
        db.session.commit()


def test_login_page_loads(client):
    assert client.get("/login").status_code == 200


def test_login_with_valid_credentials(app, client):
    create_user(app)

    response = client.post("/login", data=CREDENTIALS)

    assert response.status_code == 302
    assert b"Logout" in client.get("/").data


def test_login_with_wrong_password(app, client):
    create_user(app)

    response = client.post("/login", data={**CREDENTIALS, "password": "gresita-123"})

    assert response.status_code == 401
    assert b"Logout" not in client.get("/").data


def test_login_with_unknown_email(client):
    response = client.post("/login", data=CREDENTIALS)

    assert response.status_code == 401


def test_logout(app, client):
    create_user(app)
    client.post("/login", data=CREDENTIALS)

    client.post("/logout")

    assert b"Logout" not in client.get("/").data

# --- where the customer goes after logging in (?next=...) ---


def test_login_with_next_goes_back_to_that_page(app, client):
    create_user(app)

    response = client.post("/login?next=/cart", data=CREDENTIALS)

    assert response.status_code == 302
    assert response.headers["Location"] == "/cart"


@pytest.mark.parametrize("target", ["https://evil.com", "//evil.com", r"/\evil.com", "cart", ""])
def test_login_never_redirects_to_another_site(app, client, target):
    create_user(app)

    response = client.post("/login", query_string={"next": target}, data=CREDENTIALS)

    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_anonymous_pay_click_ends_back_in_the_cart(app, client):
    """The bug: Log in to pay -> login -> the customer must land in the cart, not on the home page."""
    create_user(app)
    with app.app_context():
        seed_products()
    client.post("/cart/add/1", data={"quantity": 1})

    cart = client.get("/cart").get_data(as_text=True)
    login_link = re.search(r'href="(/login\?next=[^"]+)">Log in to pay</a>', cart).group(1)
    response = client.post(login_link, data=CREDENTIALS)

    assert response.headers["Location"] == "/cart"
