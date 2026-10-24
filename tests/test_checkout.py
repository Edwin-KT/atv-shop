import uuid

from app.models import AuditLog, Order, Product, SecureDocument, User
from app.seed import seed_products
from app.services.users import create_admin

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


def add_document(app, email="ana@gmail.com"):
    with app.app_context():
        user = User.query.filter_by(email=email).one()
        document = SecureDocument(
            user_id=user.id,
            original_filename="talon.pdf",
            stored_filename=f"{uuid.uuid4().hex}.pdf",
            size_bytes=10,
        )
        from app.extensions import db

        db.session.add(document)
        db.session.commit()
        return document.id


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
    response = client.get("/checkout")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


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
        assert order.document_id is None
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
    assert items[0].unit_amount_cents == 18_900


def test_success_and_cancel_urls_are_sent_to_the_gateway(app, client):
    register_and_login(client)
    checkout_gear(app, client)

    session = gateway(app).sessions[last_session_id(app)]

    assert session["success_url"].endswith("/checkout/success?session_id={CHECKOUT_SESSION_ID}")
    assert "/checkout/cancel/" in session["cancel_url"]


def test_vehicle_requires_a_document(app, client):
    register_and_login(client)
    ids = product_ids(app)
    add_to_cart(client, ids, "ktm-250-exc-f")

    response = client.post("/checkout")

    assert response.status_code == 400
    with app.app_context():
        assert Order.query.count() == 0
    assert stock(app, "ktm-250-exc-f") == 5


def test_vehicle_cannot_use_someone_elses_document(app, client):
    register_and_login(client, "ion@gmail.com")
    foreign_document = add_document(app, "ion@gmail.com")
    other = register_and_login(app.test_client(), "ana@gmail.com")
    add_to_cart(other, product_ids(app), "ktm-250-exc-f")

    response = other.post("/checkout", data={"document_id": foreign_document})

    assert response.status_code == 400
    with app.app_context():
        assert Order.query.count() == 0


def test_vehicle_checkout_with_own_document(app, client):
    register_and_login(client)
    document_id = add_document(app)
    add_to_cart(client, product_ids(app), "ktm-250-exc-f")

    response = client.post("/checkout", data={"document_id": document_id})

    assert response.status_code == 303
    with app.app_context():
        assert Order.query.one().document_id == document_id


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


def test_payment_provider_failure_releases_stock(app, client):
    register_and_login(client)
    gateway(app).fail_next_create = True

    _, response = checkout_gear(app, client)

    assert response.status_code == 302
    assert "/cart" in response.headers["Location"]
    assert stock(app, "enduro-helmet-pro") == 20
    with app.app_context():
        assert Order.query.one().status == "cancelled"
        assert "payment_failed" in [e.event_type for e in AuditLog.query.all()]


# --- returning from the payment page ---

def test_paid_order_is_confirmed_and_cart_cleared(app, client):
    register_and_login(client)
    checkout_gear(app, client)
    session_id = last_session_id(app)
    gateway(app).mark_paid(session_id)

    response = client.get(f"/checkout/success?session_id={session_id}")

    assert response.status_code == 200
    assert b"Thank you for your order" in response.data
    with app.app_context():
        assert Order.query.one().status == "paid"
        assert "order_paid" in [e.event_type for e in AuditLog.query.all()]
    with client.session_transaction() as sess:
        assert sess.get("cart", {}) == {}


def test_success_page_does_not_trust_the_url_alone(app, client):
    register_and_login(client)
    checkout_gear(app, client)
    session_id = last_session_id(app)  # NOT marked as paid by the provider

    response = client.get(f"/checkout/success?session_id={session_id}")

    assert b"Payment not completed" in response.data
    with app.app_context():
        assert Order.query.one().status == "pending"


def test_refreshing_the_success_page_logs_payment_once(app, client):
    register_and_login(client)
    checkout_gear(app, client)
    session_id = last_session_id(app)
    gateway(app).mark_paid(session_id)

    client.get(f"/checkout/success?session_id={session_id}")
    client.get(f"/checkout/success?session_id={session_id}")

    with app.app_context():
        events = [e.event_type for e in AuditLog.query.all()]
        assert events.count("order_paid") == 1


def test_unknown_session_returns_404(client):
    register_and_login(client)

    assert client.get("/checkout/success?session_id=cs_nope").status_code == 404
    assert client.get("/checkout/success").status_code == 404


# --- cancelling ---

def test_cancel_releases_stock_and_expires_the_session(app, client):
    register_and_login(client)
    checkout_gear(app, client, quantity=2)
    session_id = last_session_id(app)

    assert client.get("/checkout/cancel/1").status_code == 200
    response = client.post("/orders/1/cancel")

    assert response.status_code == 302
    assert stock(app, "enduro-helmet-pro") == 20
    assert session_id in gateway(app).cancelled
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


def test_document_attached_to_an_order_cannot_be_deleted(app, client):
    register_and_login(client)
    document_id = add_document(app)
    add_to_cart(client, product_ids(app), "ktm-250-exc-f")
    client.post("/checkout", data={"document_id": document_id})

    client.post(f"/documents/{document_id}/delete")

    with app.app_context():
        assert SecureDocument.query.count() == 1