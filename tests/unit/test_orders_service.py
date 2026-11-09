"""UNIT tests for app/services/orders.py: create_order, start_payment, confirm_payment
and cancel_order, called directly with a fake payment gateway (no HTTP).

Rubric: N2.02 use case "order and pay" (stock is reserved atomically, all or
nothing); N4.02 the OutOfStockError and PaymentError exceptions; N8.02 the payment
flow; N6.01 unit tests."""

import pytest
from fake_gateway import FakeGateway

from app.exceptions import OutOfStockError, PaymentError
from app.extensions import db
from app.models import Order, OrderItem, Product, User
from app.services.cart import CartLine
from app.services.orders import cancel_order, confirm_payment, create_order, start_payment
from helpers import seed


def customer_id():
    user = User(email="ana@gmail.com", phone="0712345678")
    user.set_password("parola-sigura-123")
    db.session.add(user)
    db.session.commit()
    return user.id


def get(slug):
    return Product.query.filter_by(slug=slug).one()


def test_create_order_reserves_stock_and_freezes_the_price(app):
    seed(app)
    with app.app_context():
        helmet = get("enduro-helmet-pro")
        order = create_order(customer_id(), [CartLine(helmet, 2)])

        helmet.price_cents = 99_900  # the shop changes the price later
        db.session.commit()

        assert order.status == "pending"
        assert get("enduro-helmet-pro").stock == 18
        assert order.total_cents == 37_800  # still 2 x 189.00


def test_create_order_raises_out_of_stock_and_changes_nothing(app):
    """The first line could be reserved, the second cannot: the whole order is undone."""
    seed(app)
    with app.app_context():
        lines = [
            CartLine(get("enduro-helmet-pro"), 1),
            CartLine(get("segway-snarler-at6-l"), 3),  # only 2 in stock
        ]

        with pytest.raises(OutOfStockError):
            create_order(customer_id(), lines)

        assert get("enduro-helmet-pro").stock == 20  # the first line was rolled back too
        assert Order.query.count() == 0
        assert OrderItem.query.count() == 0


def test_payment_provider_failure_raises_and_releases_the_stock(app):
    seed(app)
    with app.app_context():
        order = create_order(customer_id(), [CartLine(get("enduro-helmet-pro"), 2)])
        gateway = FakeGateway()
        gateway.fail_next_create = True

        with pytest.raises(PaymentError):
            start_payment(order, gateway, "http://s", "http://c")

        assert order.status == "cancelled"
        assert get("enduro-helmet-pro").stock == 20


def test_confirm_payment_asks_the_provider_until_the_order_is_paid(app):
    seed(app)
    with app.app_context():
        order = create_order(customer_id(), [CartLine(get("enduro-helmet-pro"), 1)])
        gateway = FakeGateway()
        start_payment(order, gateway, "http://s", "http://c")

        assert confirm_payment(order, gateway) is False  # not paid yet
        gateway.mark_paid(order.stripe_session_id)
        assert confirm_payment(order, gateway) is True
        assert order.status == "paid" and order.paid_at is not None

        class NoNetwork(FakeGateway):
            def is_paid(self, session_id):
                raise AssertionError("an already paid order must not be checked again")

        assert confirm_payment(order, NoNetwork()) is True


def test_cancel_gives_the_stock_back_only_once(app):
    seed(app)
    with app.app_context():
        order = create_order(customer_id(), [CartLine(get("enduro-helmet-pro"), 2)])

        assert cancel_order(order) is True
        assert cancel_order(order) is False  # a second cancel does nothing

        assert get("enduro-helmet-pro").stock == 20
        assert order.status == "cancelled"


def test_cancel_changes_nothing_when_the_payment_page_cannot_be_closed(app):
    """The customer might still pay on that page, so the order must stay pending."""
    seed(app)
    with app.app_context():
        order = create_order(customer_id(), [CartLine(get("enduro-helmet-pro"), 2)])
        gateway = FakeGateway()
        start_payment(order, gateway, "http://s", "http://c")
        gateway.fail_next_expire = True

        with pytest.raises(PaymentError):
            cancel_order(order, gateway)

        assert order.status == "pending"
        assert get("enduro-helmet-pro").stock == 18  # still reserved
