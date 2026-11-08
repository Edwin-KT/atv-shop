"""INTEGRATION tests: who may open what.

Rubric: N3.04 authorization: roles (only admins reach /admin, customers get 403,
visitors go to the login page) and ownership (a customer only sees their own orders
and documents; someone else's id gives 404, so we do not even reveal it exists)."""

from io import BytesIO

import pytest

from app.cli import create_admin
from app.models import Order, SecureDocument, User
from helpers import admin_client, page, register_and_login, seed
from pdf_samples import make_pdf

# Every admin URL goes through check_admin() (bp.before_request in routes/admin.py).
ADMIN_URLS = ["/admin/", "/admin/orders", "/admin/log"]


@pytest.mark.parametrize("url", ADMIN_URLS)
def test_a_visitor_is_sent_to_the_login_page(client, url):
    response = client.get(url)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("url", ADMIN_URLS + ["/admin/products/new?type=gear"])
def test_a_customer_gets_403_on_admin_pages(client, url):
    register_and_login(client)

    assert client.get(url).status_code == 403


def test_a_customer_cannot_delete_a_product(app, client):
    ids = seed(app)
    register_and_login(client)

    assert client.post(f"/admin/products/{ids['ktm-250-exc-f']}/delete").status_code == 403
    assert "KTM 250 EXC-F" in page(client, "/")


@pytest.mark.parametrize("url", ADMIN_URLS)
def test_an_admin_gets_in(app, url):
    assert admin_client(app).get(url).status_code == 200


def test_only_an_admin_sees_the_admin_link(app, client):
    assert 'href="/admin/"' not in page(register_and_login(client), "/")
    assert 'class="nav-link nav-admin" href="/admin/"' in page(admin_client(app), "/")


def test_admins_are_only_made_on_the_server(app):
    result = app.test_cli_runner().invoke(
        args=["create-admin", "admin@shop.com", "0711111111"],
        input="parola-admin-123\nparola-admin-123\n",
    )

    assert result.exit_code == 0
    with app.app_context():
        assert User.query.filter_by(email="admin@shop.com").one().is_admin
        with pytest.raises(ValueError):
            create_admin("admin@shop.com", "0711111111", "parola-admin-123")  # duplicate
        with pytest.raises(ValueError):
            create_admin("other@shop.com", "123", "parola-admin-123")  # phone is not 10 digits


# --- ownership: my things are not yours ---


def test_another_customer_cannot_see_or_delete_my_document(app):
    owner = register_and_login(app.test_client(), "ana@gmail.com")
    owner.post("/documents/upload", data={"document": (BytesIO(make_pdf()), "talon.pdf")},
               content_type="multipart/form-data")
    intruder = register_and_login(app.test_client(), "ion@gmail.com")

    assert intruder.get("/documents/1/download").status_code == 404
    assert intruder.post("/documents/1/delete").status_code == 404
    assert "talon.pdf" not in page(intruder, "/documents")
    with app.app_context():
        assert SecureDocument.query.count() == 1


def test_another_customer_cannot_touch_my_order(app):
    ids = seed(app)
    owner = register_and_login(app.test_client(), "ana@gmail.com")
    owner.post(f"/cart/add/{ids['enduro-helmet-pro']}", data={"quantity": 1})
    owner.post("/checkout")
    with app.app_context():
        session_id = Order.query.one().stripe_session_id
    app.extensions["payment_gateway"].mark_paid(session_id)  # paid at Stripe, owner not back yet
    intruder = register_and_login(app.test_client(), "ion@gmail.com")

    assert intruder.get(f"/checkout/success?session_id={session_id}").status_code == 404
    assert intruder.get("/checkout/cancel/1").status_code == 404
    assert intruder.post("/orders/1/cancel").status_code == 404
    assert "Order #1" not in page(intruder, "/orders")
    with app.app_context():
        assert Order.query.one().status == "pending"  # the intruder's visit changed nothing
