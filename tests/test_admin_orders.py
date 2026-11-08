"""Admin orders page: a read-only list of every order."""

import re

from app.extensions import db
from app.models import Order, Product, User
from app.cli import seed_products
from app.services.cart import CartLine
from app.services.orders import create_order
from app.cli import create_admin

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
        order = create_order(user.id, [CartLine(product, quantity)])
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


def row_for(html, order_id):
    rows = re.findall(r"<tr>.*?</tr>", html, re.S)
    return next(r for r in rows if re.search(rf"<td>#{order_id}</td>", r))


def test_anonymous_is_redirected_to_login(app, client):
    response = client.get("/admin/orders")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_customer_gets_403(app):
    make_order(app)

    assert customer_client(app).get("/admin/orders").status_code == 403


def test_admin_sees_orders_with_customer_total_and_status(app):
    order_id = make_order(app, "paid", quantity=2)
    html = admin_client(app).get("/admin/orders").get_data(as_text=True)
    row = row_for(html, order_id)

    assert "ana@gmail.com" in row
    assert "378.00 EUR" in row  # 2 x 189.00, from the database
    assert '<span class="badge status-paid">paid</span>' in row
    assert 'class="table-responsive"' in html


def test_the_list_is_read_only(app):
    order_id = make_order(app, "paid")
    client = admin_client(app)
    html = client.get("/admin/orders").get_data(as_text=True)

    assert "<form" not in html.split("<main")[1]  # no buttons that change an order
    assert client.post(f"/admin/orders/{order_id}/advance").status_code == 404
    assert status_of(app, order_id) == "paid"


def test_dashboard_links_to_orders(app):
    html = admin_client(app).get("/admin/").get_data(as_text=True)

    assert 'href="/admin/orders"' in html
