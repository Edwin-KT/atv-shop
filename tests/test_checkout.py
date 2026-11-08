import re

import pytest

from app.exceptions import PaymentError
from app.models import Order, Product
from app.cli import seed_products
from app.cli import create_admin

PASSWORD = "parola-sigura-123"


def register_and_login(client, email="ana@gmail.com"):
    client.post("/register", data={"email": email, "phone": "0712345678", "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client


def product_ids(app):
    with app.app_context():
        seed_products()
        return {p.slug: p.id for p in Product.query.all()}


def stock(app, slug):
    with app.app_context():
        return Product.query.filter_by(slug=slug).one().stock


def add_to_cart(client, ids, slug, quantity=1):
    client.post(f"/cart/add/{ids[slug]}", data={"quantity": quantity})


def gateway(app):
    return app.extensions["payment_gateway"]


def last_session_id(app):
    with app.app_context():
        return Order.query.order_by(Order.id.desc()).first().stripe_session_id


def checkout_gear(app, client, quantity=1):
    ids = product_ids(app)
    add_to_cart(client, ids, "enduro-helmet-pro", quantity)
    return ids, client.post("/checkout")


# --- starting a checkout ---

def test_checkout_requires_login(client):
    response = client.post("/checkout")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_cart_has_a_csrf_pay_button_that_posts_to_checkout(app, client):
    register_and_login(client)
    add_to_cart(client, product_ids(app), "enduro-helmet-pro")
    html = client.get("/cart").get_data(as_text=True)

    form = re.search(r'<form method="post" action="/checkout">.*?</form>', html, re.S).group(0)
    assert 'name="csrf_token"' in form
    assert "Pay with card" in form


def test_get_checkout_goes_back_to_the_cart(client):
    """After logging in, Flask-Login sends the customer back to /checkout with a GET."""
    register_and_login(client)

    response = client.get("/checkout")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/cart")


def test_empty_cart_redirects_back_to_cart(client):
    register_and_login(client)

    response = client.post("/checkout")

    assert response.status_code == 302
    assert "/cart" in response.headers["Location"]


def test_checkout_creates_order_reserves_stock_and_redirects_to_payment(app, client):
    register_and_login(client)

    _, response = checkout_gear(app, client, quantity=2)

    assert response.status_code == 303
    assert response.headers["Location"].startswith("https://pay.example.test/")
    assert stock(app, "enduro-helmet-pro") == 18
    with app.app_context():
        order = Order.query.one()
        assert order.status == "pending"
        assert order.stripe_session_id is not None
    with client.session_transaction() as sess:
        assert sess["cart"]  # cart is only cleared after the payment is confirmed


def test_payment_amounts_come_from_the_database(app, client):
    register_and_login(client)
    ids = product_ids(app)
    client.post(
        f"/cart/add/{ids['enduro-helmet-pro']}", data={"quantity": 1, "price_cents": 1}
    )

    client.post("/checkout", data={"price_cents": 1})

    items = gateway(app).sessions[last_session_id(app)]["items"]
    assert items == [("Enduro Helmet Pro", 18_900, 1)]  # not the 1 cent sent by the client


def test_success_and_cancel_urls_are_sent_to_the_gateway(app, client):
    register_and_login(client)
    checkout_gear(app, client)

    session = gateway(app).sessions[last_session_id(app)]

    assert session["success_url"].endswith("/checkout/success?session_id={CHECKOUT_SESSION_ID}")
    assert "/checkout/cancel/" in session["cancel_url"]




def test_out_of_stock_at_checkout_creates_no_order(app, client):
    register_and_login(client)
    ids = product_ids(app)
    add_to_cart(client, ids, "enduro-helmet-pro", 2)
    with app.app_context():  # someone else buys the stock in the meantime
        from app.extensions import db

        Product.query.filter_by(slug="enduro-helmet-pro").one().stock = 1
        db.session.commit()

    response = client.post("/checkout")

    assert response.status_code == 302
    assert "/cart" in response.headers["Location"]
    with app.app_context():
        assert Order.query.count() == 0
    assert stock(app, "enduro-helmet-pro") == 1


def test_payment_provider_failure_releases_stock(app, client, log_text):
    register_and_login(client)
    gateway(app).fail_next_create = True

    _, response = checkout_gear(app, client)

    assert response.status_code == 302
    assert "/cart" in response.headers["Location"]
    assert stock(app, "enduro-helmet-pro") == 20
    with app.app_context():
        assert Order.query.one().status == "cancelled"
    assert "event=payment_failed" in log_text()


# --- returning from the payment page ---

def test_paid_order_is_confirmed_and_cart_cleared(app, client, log_text):
    register_and_login(client)
    checkout_gear(app, client)
    session_id = last_session_id(app)
    gateway(app).mark_paid(session_id)

    response = client.get(f"/checkout/success?session_id={session_id}")

    assert response.status_code == 200
    assert b"Thank you for your order" in response.data
    with app.app_context():
        assert Order.query.one().status == "paid"
    with client.session_transaction() as sess:
        assert sess.get("cart", {}) == {}
    assert "event=order_paid order_id=1" in log_text()


def test_success_page_does_not_trust_the_url_alone(app, client):
    register_and_login(client)
    checkout_gear(app, client)
    session_id = last_session_id(app)  # NOT marked as paid by the provider

    response = client.get(f"/checkout/success?session_id={session_id}")

    assert b"Payment not completed" in response.data
    with app.app_context():
        assert Order.query.one().status == "pending"


def test_refreshing_the_success_page_logs_payment_once(app, client, log_text):
    register_and_login(client)
    checkout_gear(app, client)
    session_id = last_session_id(app)
    gateway(app).mark_paid(session_id)

    client.get(f"/checkout/success?session_id={session_id}")
    client.get(f"/checkout/success?session_id={session_id}")

    assert log_text().count("event=order_paid") == 1


@pytest.mark.parametrize("session_id", ["cs_nope", "", "' OR 1=1 --"])
def test_unknown_session_returns_404(client, session_id):
    register_and_login(client)

    assert client.get("/checkout/success", query_string={"session_id": session_id}).status_code == 404


# --- cancelling ---

def test_cancel_releases_stock_and_expires_the_session(app, client):
    register_and_login(client)
    checkout_gear(app, client, quantity=2)
    session_id = last_session_id(app)

    assert client.get("/checkout/cancel/1").status_code == 200
    response = client.post("/orders/1/cancel")

    assert response.status_code == 302
    assert stock(app, "enduro-helmet-pro") == 20
    assert session_id in gateway(app).expired  # the Stripe page can no longer be paid
    with app.app_context():
        assert Order.query.one().status == "cancelled"


def test_paid_order_cannot_be_cancelled(app, client):
    register_and_login(client)
    checkout_gear(app, client)
    gateway(app).mark_paid(last_session_id(app))

    client.post("/orders/1/cancel")

    assert stock(app, "enduro-helmet-pro") == 19
    with app.app_context():
        assert Order.query.one().status == "paid"


def test_cancel_requires_post(app, client):
    register_and_login(client)
    checkout_gear(app, client)

    assert client.get("/orders/1/cancel").status_code == 405


# --- ownership ---

def test_other_users_cannot_touch_my_order(app, client):
    register_and_login(client)
    checkout_gear(app, client)
    session_id = last_session_id(app)
    gateway(app).mark_paid(session_id)
    intruder = register_and_login(app.test_client(), "ion@gmail.com")

    assert intruder.get(f"/checkout/success?session_id={session_id}").status_code == 404
    assert intruder.get("/checkout/cancel/1").status_code == 404
    assert intruder.post("/orders/1/cancel").status_code == 404
    assert b"Order #1" not in intruder.get("/orders").data


def test_orders_page_lists_my_orders(app, client):
    register_and_login(client)
    checkout_gear(app, client, quantity=2)

    html = client.get("/orders").get_data(as_text=True)

    assert "Order #1" in html
    assert "Enduro Helmet Pro" in html
    assert "378.00 EUR" in html


# --- history stays intact ---

def test_ordered_product_cannot_be_deleted(app):
    customer = register_and_login(app.test_client())
    ids, _ = checkout_gear(app, customer)
    with app.app_context():
        create_admin("boss@gmail.com", "0711111111", "parola-admin-123")
    admin = app.test_client()
    admin.post("/login", data={"email": "boss@gmail.com", "password": "parola-admin-123"})

    admin.post(f"/admin/products/{ids['enduro-helmet-pro']}/delete")

    with app.app_context():
        assert Product.query.filter_by(slug="enduro-helmet-pro").count() == 1


# --- success page: ownership, refresh, provider errors ---

def count_payment_checks(monkeypatch, app):
    """Wrap the fake gateway so the test can see how often Stripe would be asked."""
    fake = gateway(app)
    calls = []
    original = fake.is_paid

    def spy(session_id):
        calls.append(session_id)
        return original(session_id)

    monkeypatch.setattr(fake, "is_paid", spy)
    return calls


def test_other_user_opening_my_success_link_changes_nothing(app, client, monkeypatch, log_text):
    register_and_login(client)
    checkout_gear(app, client)
    session_id = last_session_id(app)
    gateway(app).mark_paid(session_id)  # paid at Stripe, owner has not returned yet
    calls = count_payment_checks(monkeypatch, app)
    intruder = register_and_login(app.test_client(), "ion@gmail.com")

    response = intruder.get(f"/checkout/success?session_id={session_id}")

    assert response.status_code == 404
    assert calls == []
    with app.app_context():
        assert Order.query.one().status == "pending"
    assert "event=order_paid" not in log_text()


def test_refreshing_the_success_page_keeps_stock_and_paid_at(app, client, monkeypatch):
    register_and_login(client)
    checkout_gear(app, client)
    session_id = last_session_id(app)
    gateway(app).mark_paid(session_id)
    calls = count_payment_checks(monkeypatch, app)

    assert client.get(f"/checkout/success?session_id={session_id}").status_code == 200
    with app.app_context():
        first_paid_at = Order.query.one().paid_at
    assert client.get(f"/checkout/success?session_id={session_id}").status_code == 200

    assert stock(app, "enduro-helmet-pro") == 19  # reserved once, at checkout
    assert len(calls) == 1  # an already paid order is not checked again
    with app.app_context():
        order = Order.query.one()
        assert order.status == "paid"
        assert order.paid_at == first_paid_at


def test_provider_error_on_success_redirects_to_orders(app, client, monkeypatch, log_text):
    register_and_login(client)
    checkout_gear(app, client)
    session_id = last_session_id(app)

    def provider_down(_session_id):
        raise PaymentError("Stripe is down")

    monkeypatch.setattr(gateway(app), "is_paid", provider_down)

    response = client.get(f"/checkout/success?session_id={session_id}")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/orders")
    with app.app_context():
        assert Order.query.one().status == "pending"
    assert "event=payment_check_failed" in log_text()


# --- order status after payment, as the customer sees it ---

def paid_and_set_status(app, client, status):
    """Checkout, pay at the (fake) provider, return to the shop, then move the order on."""
    register_and_login(client)
    checkout_gear(app, client)
    session_id = last_session_id(app)
    gateway(app).mark_paid(session_id)
    client.get(f"/checkout/success?session_id={session_id}")
    with app.app_context():
        from app.extensions import db

        Order.query.one().status = status
        db.session.commit()
    return session_id


def test_success_page_opened_twice_records_the_payment_once(app, client, log_text):
    session_id = paid_and_set_status(app, client, "paid")

    response = client.get(f"/checkout/success?session_id={session_id}")

    assert b"Thank you for your order" in response.data
    with app.app_context():
        assert Order.query.one().status == "paid"
    assert log_text().count("event=order_paid") == 1


def test_paid_order_cannot_be_cancelled_and_keeps_stock(app, client):
    paid_and_set_status(app, client, "paid")

    client.post("/orders/1/cancel")

    assert stock(app, "enduro-helmet-pro") == 19
    with app.app_context():
        assert Order.query.one().status == "paid"


# --- cancel page (Stripe's cancel_url) shows the order's real status ---

def cancel_page(client, order_id=1):
    return client.get(f"/checkout/cancel/{order_id}").get_data(as_text=True)


def test_cancel_page_for_a_pending_order_offers_to_cancel(app, client):
    register_and_login(client)
    checkout_gear(app, client)
    html = cancel_page(client)

    assert "Payment cancelled" in html
    assert "was not paid" in html
    assert 'action="/orders/1/cancel"' in html


def test_cancel_page_for_a_paid_order_says_it_is_paid(app, client):
    paid_and_set_status(app, client, "paid")
    html = cancel_page(client)

    assert "This order is already paid" in html
    assert re.search(r'href="/orders"\s*>My orders</a>', html)
    assert "was not paid" not in html
    assert "Cancel order" not in html


def test_cancel_page_for_a_cancelled_order_says_it_was_cancelled(app, client):
    register_and_login(client)
    checkout_gear(app, client)
    client.post("/orders/1/cancel")
    html = cancel_page(client)

    assert "Order cancelled" in html
    assert "back in stock" in html
    assert "was not paid" not in html
    assert "Cancel order" not in html
