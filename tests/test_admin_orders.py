"""Admin order tracking: /admin/orders and forward-only status changes."""

import re

import pytest

from app.extensions import db
from app.models import AuditLog, Order, Product, User
from app.seed import seed_products
from app.services.cart import CartLine
from app.services.orders import create_order
from app.services.users import create_admin

ADMIN = {"email": "boss@gmail.com", "password": "parola-admin-123"}
CUSTOMER = {"email": "ana@gmail.com", "password": "parola-sigura-123"}


def make_order(app, status="paid", quantity=1):
    """A real order (stock reserved by create_order), then put in `status`."""
    with app.app_context():
        if not Product.query.count():
            seed_products()
        user = User.query.filter_by(email=CUSTOMER["email"]).first()
        if user is None:
            user = User(email=CUSTOMER["email"], phone="0712345678")
            user.set_password(CUSTOMER["password"])
            db.session.add(user)
            db.session.commit()
        product = Product.query.filter_by(slug="enduro-helmet-pro").one()
        order = create_order(user.id, [CartLine(product, quantity)], None)
        order.status = status
        db.session.commit()
        return order.id


def admin_client(app):
    with app.app_context():
        create_admin(ADMIN["email"], "0711111111", ADMIN["password"])
    client = app.test_client()
    client.post("/login", data=ADMIN)
    return client


def customer_client(app):
    client = app.test_client()
    client.post("/login", data=CUSTOMER)
    return client


def status_of(app, order_id):
    with app.app_context():
        return db.session.get(Order, order_id).status


def status_events(app):
    with app.app_context():
        return AuditLog.query.filter_by(event_type="order_status_changed").all()


def helmet_stock(app):
    with app.app_context():
        return Product.query.filter_by(slug="enduro-helmet-pro").one().stock


def advance(client, order_id, expected):
    return client.post(f"/admin/orders/{order_id}/advance", data={"status": expected})


def row_for(html, order_id):
    rows = re.findall(r"<tr>.*?</tr>", html, re.S)
    return next(r for r in rows if re.search(rf"<td>#{order_id}</td>", r))


# --- access control ---


def test_anonymous_is_redirected_to_login(app, client):
    order_id = make_order(app)

    for response in (client.get("/admin/orders"), advance(client, order_id, "paid")):
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
    assert status_of(app, order_id) == "paid"


def test_customer_gets_403_and_cannot_change_status(app):
    order_id = make_order(app)
    client = customer_client(app)

    assert client.get("/admin/orders").status_code == 403
    assert advance(client, order_id, "paid").status_code == 403
    assert status_of(app, order_id) == "paid"
    assert status_events(app) == []


# --- list ---


def test_admin_sees_orders_with_customer_total_and_status(app):
    order_id = make_order(app, "shipped", quantity=2)
    html = admin_client(app).get("/admin/orders").get_data(as_text=True)
    row = row_for(html, order_id)

    assert "ana@gmail.com" in row
    assert "378.00" in row  # 2 x 189.00, from the database
    assert "Shipped" in row
    assert "Mark as delivered" in row
    assert 'class="table-responsive"' in html


def test_dashboard_links_to_orders(app):
    html = admin_client(app).get("/admin/").get_data(as_text=True)

    assert 'href="/admin/orders"' in html


def test_advance_form_posts_with_csrf_token_and_current_status(app):
    order_id = make_order(app, "paid")
    row = row_for(admin_client(app).get("/admin/orders").get_data(as_text=True), order_id)

    assert f'action="/admin/orders/{order_id}/advance"' in row
    assert 'name="csrf_token"' in row
    assert re.search(r'name="status"\s+value="paid"', row)


def test_filter_by_status(app):
    paid_id = make_order(app, "paid")
    shipped_id = make_order(app, "shipped")
    html = admin_client(app).get("/admin/orders?status=shipped").get_data(as_text=True)

    assert f"<td>#{shipped_id}</td>" in html
    assert f"<td>#{paid_id}</td>" not in html


def test_unknown_status_filter_shows_every_order(app):
    ids = [make_order(app, s) for s in ("pending", "paid", "shipped", "cancelled")]
    response = admin_client(app).get("/admin/orders?status=lost-in-the-mail")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    for order_id in ids:
        assert f"<td>#{order_id}</td>" in html


# --- moving forward ---


def test_admin_advances_one_step_and_it_is_audited(app):
    order_id = make_order(app, "paid")
    client = admin_client(app)

    response = advance(client, order_id, "paid")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/orders")
    assert status_of(app, order_id) == "processing"
    events = status_events(app)
    assert len(events) == 1
    with app.app_context():
        admin_id = User.query.filter_by(email=ADMIN["email"]).one().id
    assert events[0].user_id == admin_id
    assert events[0].details == f"order_id={order_id} paid->processing"


def test_full_path_to_delivered(app):
    order_id = make_order(app, "paid")
    client = admin_client(app)

    for expected in ("paid", "processing", "shipped"):
        advance(client, order_id, expected)

    assert status_of(app, order_id) == "delivered"
    assert len(status_events(app)) == 3
    row = row_for(client.get("/admin/orders").get_data(as_text=True), order_id)
    assert "Mark as" not in row


def test_double_post_moves_one_step_and_audits_once(app):
    order_id = make_order(app, "paid")
    client = admin_client(app)

    advance(client, order_id, "paid")
    advance(client, order_id, "paid")  # double click, or a second admin

    assert status_of(app, order_id) == "processing"
    assert len(status_events(app)) == 1


def test_a_step_cannot_be_skipped(app):
    order_id = make_order(app, "paid")

    advance(admin_client(app), order_id, "shipped")  # pretends to be further along

    assert status_of(app, order_id) == "paid"
    assert status_events(app) == []


@pytest.mark.parametrize("status", ["pending", "cancelled", "delivered"])
def test_orders_that_cannot_move_have_no_button_and_reject_posts(app, status):
    order_id = make_order(app, status)
    client = admin_client(app)

    row = row_for(client.get("/admin/orders").get_data(as_text=True), order_id)
    assert "Mark as" not in row

    advance(client, order_id, status)
    assert status_of(app, order_id) == status
    assert status_events(app) == []


def test_advancing_does_not_change_stock(app):
    order_id = make_order(app, "paid", quantity=2)
    stock_after_checkout = helmet_stock(app)
    client = admin_client(app)

    for expected in ("paid", "processing", "shipped"):
        advance(client, order_id, expected)

    assert helmet_stock(app) == stock_after_checkout


def test_unknown_order_returns_404(app):
    assert advance(admin_client(app), 999, "paid").status_code == 404
