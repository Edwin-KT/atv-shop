import pytest
from fake_gateway import FakeGateway
from sqlalchemy.exc import IntegrityError

from app.exceptions import EmptyCartError, OutOfStockError, PaymentError
from app.extensions import db
from app.models import Order, OrderItem, Product, User
from app.seed import seed_products
from app.services.cart import CartLine
from app.services.orders import (
    advance_order_status,
    cancel_order,
    confirm_payment,
    create_order,
    start_payment,
)
from app.services.payment_interface import PaymentItem


def setup_data():
    seed_products()
    user = User(email="ana@gmail.com", phone="0712345678")
    user.set_password("parola-sigura-123")
    db.session.add(user)
    db.session.commit()
    return user.id


def get(slug):
    return Product.query.filter_by(slug=slug).one()


def test_order_reserves_stock_and_total_is_derived(app):
    with app.app_context():
        user_id = setup_data()

        order = create_order(user_id, [CartLine(get("enduro-helmet-pro"), 2)], None)

        assert order.status == "pending"
        assert order.total_cents == 37_800
        assert get("enduro-helmet-pro").stock == 18


def test_price_is_frozen_at_purchase_time(app):
    with app.app_context():
        user_id = setup_data()
        helmet = get("enduro-helmet-pro")
        order = create_order(user_id, [CartLine(helmet, 2)], None)

        helmet.price_cents = 99_900
        db.session.commit()

        assert order.total_cents == 37_800


def test_failed_line_cancels_the_whole_order(app):
    with app.app_context():
        user_id = setup_data()
        lines = [
            CartLine(get("enduro-helmet-pro"), 1),
            CartLine(get("segway-snarler-at6-l"), 3),  # only 2 in stock
        ]

        with pytest.raises(OutOfStockError):
            create_order(user_id, lines, None)

        assert get("enduro-helmet-pro").stock == 20  # first line rolled back too
        assert Order.query.count() == 0
        assert OrderItem.query.count() == 0


def test_empty_cart_is_rejected(app):
    with app.app_context():
        user_id = setup_data()

        with pytest.raises(EmptyCartError):
            create_order(user_id, [], None)


def test_cancel_restores_stock_only_once(app):
    with app.app_context():
        user_id = setup_data()
        order = create_order(user_id, [CartLine(get("enduro-helmet-pro"), 2)], None)

        assert cancel_order(order) is True
        assert cancel_order(order) is False

        assert get("enduro-helmet-pro").stock == 20
        assert order.status == "cancelled"


def test_payment_start_failure_releases_stock(app):
    with app.app_context():
        user_id = setup_data()
        order = create_order(user_id, [CartLine(get("enduro-helmet-pro"), 2)], None)
        gateway = FakeGateway()
        gateway.fail_next_create = True

        with pytest.raises(PaymentError):
            start_payment(order, gateway, "http://s", "http://c")

        assert order.status == "cancelled"
        assert get("enduro-helmet-pro").stock == 20


def test_payment_items_use_database_prices(app):
    with app.app_context():
        user_id = setup_data()
        order = create_order(user_id, [CartLine(get("enduro-helmet-pro"), 2)], None)
        gateway = FakeGateway()

        session = start_payment(order, gateway, "http://s", "http://c")

        assert gateway.sessions[session.session_id]["items"] == [
            PaymentItem("Enduro Helmet Pro", 18_900, 2)
        ]
        assert order.stripe_session_id == session.session_id


def test_confirm_payment_flow(app):
    with app.app_context():
        user_id = setup_data()
        order = create_order(user_id, [CartLine(get("enduro-helmet-pro"), 1)], None)
        gateway = FakeGateway()
        start_payment(order, gateway, "http://s", "http://c")

        assert confirm_payment(order, gateway) is False  # not paid yet
        assert order.status == "pending"

        gateway.mark_paid(order.stripe_session_id)
        assert confirm_payment(order, gateway) is True
        assert order.status == "paid"
        assert order.paid_at is not None
        assert confirm_payment(order, gateway) is True  # idempotent


def test_payment_for_a_different_order_is_rejected(app):
    with app.app_context():
        user_id = setup_data()
        order = create_order(user_id, [CartLine(get("enduro-helmet-pro"), 1)], None)
        gateway = FakeGateway()
        other = gateway.create_checkout_session("999", [], "http://s", "http://c")
        gateway.mark_paid(other.session_id)
        order.stripe_session_id = other.session_id

        with pytest.raises(PaymentError):
            confirm_payment(order, gateway)
        assert order.status == "pending"


def test_paid_order_cannot_be_cancelled(app):
    with app.app_context():
        user_id = setup_data()
        order = create_order(user_id, [CartLine(get("enduro-helmet-pro"), 1)], None)
        gateway = FakeGateway()
        start_payment(order, gateway, "http://s", "http://c")
        gateway.mark_paid(order.stripe_session_id)
        confirm_payment(order, gateway)

        assert cancel_order(order, gateway) is False
        assert get("enduro-helmet-pro").stock == 19


# --- forward-only status after payment ---

def paid_order(user_id, status="paid"):
    order = create_order(user_id, [CartLine(get("enduro-helmet-pro"), 1)], None)
    order.status = status
    db.session.commit()
    return order


def test_advance_order_status_walks_forward_one_step_at_a_time(app):
    with app.app_context():
        order = paid_order(setup_data())

        assert advance_order_status(order.id, "paid") == "processing"
        assert advance_order_status(order.id, "processing") == "shipped"
        assert advance_order_status(order.id, "shipped") == "delivered"
        assert db.session.get(Order, order.id).status == "delivered"


@pytest.mark.parametrize("status", ["pending", "cancelled", "delivered"])
def test_orders_without_a_next_step_do_not_move(app, status):
    with app.app_context():
        order = paid_order(setup_data(), status)

        assert advance_order_status(order.id, status) is None
        assert db.session.get(Order, order.id).status == status


def test_unknown_expected_status_changes_nothing(app):
    with app.app_context():
        order = paid_order(setup_data())

        assert advance_order_status(order.id, "lost") is None
        assert db.session.get(Order, order.id).status == "paid"


def test_stale_expected_status_changes_nothing(app):
    with app.app_context():
        order = paid_order(setup_data())
        advance_order_status(order.id, "paid")

        assert advance_order_status(order.id, "paid") is None  # someone was faster
        assert db.session.get(Order, order.id).status == "processing"


@pytest.mark.parametrize(
    "status, expected",
    [("pending", False), ("paid", True), ("processing", True),
     ("shipped", True), ("delivered", True), ("cancelled", False)],
)
def test_is_paid_covers_every_status_after_payment(status, expected):
    assert Order(status=status).is_paid is expected


def test_confirm_payment_does_not_ask_stripe_again_after_shipping(app):
    with app.app_context():
        order = paid_order(setup_data(), "shipped")

        class NoNetwork(FakeGateway):
            def get_payment_result(self, session_id):
                raise AssertionError("an already paid order must not be checked again")

        assert confirm_payment(order, NoNetwork()) is True
        assert order.status == "shipped"


def test_database_rejects_unknown_order_status(app):
    with app.app_context():
        order = paid_order(setup_data())
        order.status = "lost"
        with pytest.raises(IntegrityError):
            db.session.commit()
