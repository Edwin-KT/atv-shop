"""INTEGRATION tests: ordering and paying through the real routes, with a fake Stripe
(FakeGateway, plugged in through the PaymentGateway interface).

Rubric: N2.02 use case "order, pay, cancel"; N8.02 online payment (Stripe Checkout);
N4.02 exceptions handled in the routes (OutOfStockError, PaymentError); N3.04 only
logged-in customers can order."""

import re

import pytest

from app.exceptions import PaymentError
from app.extensions import db
from app.models import Order, Product
from helpers import page, register_and_login, seed


@pytest.fixture()
def customer(app, client):
    """A logged-in customer; the shop has its sample products."""
    seed(app)
    return register_and_login(client)


def gateway(app):
    return app.extensions["payment_gateway"]


def stock(app, slug="enduro-helmet-pro"):
    with app.app_context():
        return Product.query.filter_by(slug=slug).one().stock


def the_order(app):
    with app.app_context():
        return Order.query.one()


def checkout(app, client, quantity=1):
    """Put helmets in the cart and press "Pay with card"; returns the response."""
    with app.app_context():
        helmet_id = Product.query.filter_by(slug="enduro-helmet-pro").one().id
    client.post(f"/cart/add/{helmet_id}", data={"quantity": quantity})
    return client.post("/checkout")


def pay_at_stripe(app):
    session_id = the_order(app).stripe_session_id
    gateway(app).mark_paid(session_id)
    return session_id


def count_payment_checks(monkeypatch, app):
    """Wrap the fake gateway so a test can see how often Stripe would be asked."""
    calls, original = [], gateway(app).is_paid

    def spy(session_id):
        calls.append(session_id)
        return original(session_id)

    monkeypatch.setattr(gateway(app), "is_paid", spy)
    return calls


# --- starting a checkout ---


def test_checkout_requires_login(client):
    response = client.post("/checkout")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_an_empty_cart_goes_back_to_the_cart(customer):
    response = customer.post("/checkout")

    assert response.headers["Location"].endswith("/cart")


def test_checkout_reserves_stock_and_sends_the_customer_to_stripe(app, customer):
    response = checkout(app, customer, quantity=2)

    assert response.status_code == 303
    assert response.headers["Location"].startswith("https://pay.example.test/")
    assert stock(app) == 18  # reserved now, before paying
    order = the_order(app)
    assert order.status == "pending" and order.stripe_session_id
    with customer.session_transaction() as session:
        assert session["cart"]  # emptied only after the payment is confirmed


def test_stripe_gets_the_database_prices_and_our_return_urls(app, customer):
    checkout(app, customer)

    sent = gateway(app).sessions[the_order(app).stripe_session_id]

    assert sent["items"] == [("Enduro Helmet Pro", 18_900, 1)]
    assert sent["success_url"].endswith("/checkout/success?session_id={CHECKOUT_SESSION_ID}")
    assert "/checkout/cancel/1" in sent["cancel_url"]


def test_out_of_stock_at_checkout_creates_no_order(app, customer):
    """OutOfStockError: someone else bought the last helmets in the meantime."""
    with app.app_context():
        helmet_id = Product.query.filter_by(slug="enduro-helmet-pro").one().id
    customer.post(f"/cart/add/{helmet_id}", data={"quantity": 2})
    with app.app_context():
        Product.query.filter_by(slug="enduro-helmet-pro").one().stock = 1
        db.session.commit()

    response = customer.post("/checkout")

    assert response.headers["Location"].endswith("/cart")
    assert "Not enough stock for Enduro Helmet Pro." in page(customer, "/cart")
    with app.app_context():
        assert Order.query.count() == 0
    assert stock(app) == 1


def test_a_payment_provider_failure_releases_the_stock(app, customer, log_text):
    """PaymentError: Stripe is down, so the order is cancelled and nothing stays reserved."""
    gateway(app).fail_next_create = True

    response = checkout(app, customer)

    assert response.headers["Location"].endswith("/cart")
    assert stock(app) == 20
    assert the_order(app).status == "cancelled"
    assert "event=payment_failed" in log_text()


# --- coming back from Stripe ---


def test_a_paid_order_is_confirmed_and_the_cart_emptied(app, customer, log_text):
    checkout(app, customer)
    session_id = pay_at_stripe(app)

    response = customer.get(f"/checkout/success?session_id={session_id}")

    assert b"Thank you for your order" in response.data
    assert the_order(app).status == "paid"
    with customer.session_transaction() as session:
        assert session.get("cart", {}) == {}
    assert "event=order_paid order_id=1" in log_text()


def test_the_success_page_does_not_trust_the_url_alone(app, customer):
    checkout(app, customer)
    session_id = the_order(app).stripe_session_id  # NOT paid at Stripe

    response = customer.get(f"/checkout/success?session_id={session_id}")

    assert b"Payment not completed" in response.data
    assert the_order(app).status == "pending"


def test_refreshing_the_success_page_changes_nothing(app, customer, monkeypatch, log_text):
    checkout(app, customer)
    session_id = pay_at_stripe(app)
    calls = count_payment_checks(monkeypatch, app)

    customer.get(f"/checkout/success?session_id={session_id}")
    first_paid_at = the_order(app).paid_at
    customer.get(f"/checkout/success?session_id={session_id}")

    assert stock(app) == 19  # reserved once, at checkout
    assert len(calls) == 1  # a paid order is not checked at Stripe again
    assert the_order(app).paid_at == first_paid_at
    assert log_text().count("event=order_paid") == 1


@pytest.mark.parametrize("session_id", ["cs_nope", "", "' OR 1=1 --"])
def test_an_unknown_session_id_returns_404(customer, session_id):
    assert customer.get("/checkout/success", query_string={"session_id": session_id}).status_code == 404


def test_stripe_being_down_on_return_sends_the_customer_to_my_orders(app, customer, monkeypatch, log_text):
    checkout(app, customer)

    def stripe_down(_session_id):
        raise PaymentError("Stripe is down")

    monkeypatch.setattr(gateway(app), "is_paid", stripe_down)

    response = customer.get(f"/checkout/success?session_id={the_order(app).stripe_session_id}")

    assert response.headers["Location"].endswith("/orders")
    assert the_order(app).status == "pending"
    assert "event=payment_check_failed" in log_text()


# --- cancelling ---


def test_cancel_releases_the_stock_and_closes_the_stripe_page(app, customer):
    checkout(app, customer, quantity=2)
    session_id = the_order(app).stripe_session_id

    response = customer.post("/orders/1/cancel")

    assert response.status_code == 302
    assert stock(app) == 20
    assert session_id in gateway(app).expired  # the Stripe page can no longer be paid
    assert the_order(app).status == "cancelled"


def test_a_paid_order_cannot_be_cancelled(app, customer):
    checkout(app, customer)
    pay_at_stripe(app)

    customer.post("/orders/1/cancel")

    assert stock(app) == 19
    assert the_order(app).status == "paid"


def test_cancel_is_refused_when_stripe_cannot_close_the_payment_page(app, customer, log_text):
    checkout(app, customer)
    gateway(app).fail_next_expire = True

    response = customer.post("/orders/1/cancel", follow_redirects=True)

    assert "the order was not cancelled" in response.get_data(as_text=True)
    assert the_order(app).status == "pending"
    assert stock(app) == 19  # still reserved: the customer may still pay
    assert "event=order_cancel_failed" in log_text()


def test_cancel_needs_a_post(app, customer):
    checkout(app, customer)

    assert customer.get("/orders/1/cancel").status_code == 405


def test_the_cancel_page_offers_to_cancel_only_an_unpaid_order(app, customer):
    checkout(app, customer)

    pending = page(customer, "/checkout/cancel/1")
    assert "Payment cancelled" in pending and 'action="/orders/1/cancel"' in pending

    customer.get(f"/checkout/success?session_id={pay_at_stripe(app)}")
    paid = page(customer, "/checkout/cancel/1")
    assert "This order is already paid" in paid and "Cancel order" not in paid


def test_my_orders_lists_items_total_and_status(app, customer):
    checkout(app, customer, quantity=2)

    html = page(customer, "/orders")

    assert "Order #1" in html and "Enduro Helmet Pro" in html
    assert "378.00 EUR" in html
    assert re.search(r'<span class="badge status-pending">pending</span>', html)


def test_my_orders_shows_a_payment_made_after_the_stripe_tab_was_closed(app, customer, log_text):
    """The customer paid but never came back to the success page."""
    checkout(app, customer)
    pay_at_stripe(app)

    html = page(customer, "/orders")

    assert '<span class="badge status-paid">paid</span>' in html
    assert the_order(app).status == "paid"
    assert "event=order_paid" in log_text()


def test_my_orders_still_loads_when_stripe_is_down(app, customer, monkeypatch, log_text):
    checkout(app, customer)

    def stripe_down(_session_id):
        raise PaymentError("Stripe is down")

    monkeypatch.setattr(gateway(app), "is_paid", stripe_down)

    html = page(customer, "/orders")

    assert '<span class="badge status-pending">pending</span>' in html
    assert "a status may be out of date" in html
    assert "event=payment_check_failed" in log_text()


def test_my_orders_does_not_ask_stripe_about_finished_orders(app, customer, monkeypatch):
    checkout(app, customer)
    customer.get(f"/checkout/success?session_id={pay_at_stripe(app)}")  # now paid
    calls = count_payment_checks(monkeypatch, app)

    page(customer, "/orders")

    assert calls == []
