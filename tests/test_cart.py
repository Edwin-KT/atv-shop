from app import create_app
from app.extensions import db
from app.models import Product
from app.seed import seed_products


def seed(app):
    """Seed products and return {slug: id}."""
    with app.app_context():
        seed_products()
        return {p.slug: p.id for p in Product.query.all()}


def cart_in_session(client):
    with client.session_transaction() as sess:
        return sess.get("cart", {})


def test_empty_cart_page(client):
    html = client.get("/cart").get_data(as_text=True)

    assert "Your cart is empty" in html


def test_added_product_appears_in_cart_with_total(app, client):
    ids = seed(app)

    response = client.post(f"/cart/add/{ids['enduro-helmet-pro']}", data={"quantity": 2})
    html = client.get("/cart").get_data(as_text=True)

    assert response.status_code == 302
    assert "Enduro Helmet Pro" in html
    assert "378.00 EUR" in html  # 2 x 189.00


def test_adding_same_product_twice_increases_quantity(app, client):
    ids = seed(app)
    url = f"/cart/add/{ids['enduro-helmet-pro']}"

    client.post(url, data={"quantity": 1})
    client.post(url, data={"quantity": 1})

    assert cart_in_session(client) == {str(ids["enduro-helmet-pro"]): 2}


def test_quantity_is_capped_by_stock(app, client):
    ids = seed(app)

    client.post(f"/cart/add/{ids['segway-snarler-at6-l']}", data={"quantity": 5})

    assert cart_in_session(client) == {str(ids["segway-snarler-at6-l"]): 2}


def test_out_of_stock_product_cannot_be_added(app, client):
    ids = seed(app)
    with app.app_context():
        Product.query.filter_by(slug="off-road-boots-x").one().stock = 0
        db.session.commit()

    client.post(f"/cart/add/{ids['off-road-boots-x']}", data={"quantity": 1})

    assert cart_in_session(client) == {}


def test_invalid_quantity_falls_back_to_one(app, client):
    ids = seed(app)

    client.post(f"/cart/add/{ids['enduro-helmet-pro']}", data={"quantity": "abc"})

    assert cart_in_session(client) == {str(ids["enduro-helmet-pro"]): 1}


def test_update_quantity(app, client):
    ids = seed(app)
    pid = ids["riding-gloves-trail"]
    client.post(f"/cart/add/{pid}", data={"quantity": 1})

    client.post(f"/cart/update/{pid}", data={"quantity": 4})

    assert cart_in_session(client) == {str(pid): 4}


def test_update_to_zero_removes_item(app, client):
    ids = seed(app)
    pid = ids["riding-gloves-trail"]
    client.post(f"/cart/add/{pid}", data={"quantity": 1})

    client.post(f"/cart/update/{pid}", data={"quantity": 0})

    assert cart_in_session(client) == {}


def test_remove_item(app, client):
    ids = seed(app)
    pid = ids["riding-gloves-trail"]
    client.post(f"/cart/add/{pid}", data={"quantity": 1})

    client.post(f"/cart/remove/{pid}")

    assert cart_in_session(client) == {}


def test_unknown_product_returns_404(client):
    assert client.post("/cart/add/9999", data={"quantity": 1}).status_code == 404


def test_price_comes_from_database_not_from_client(app, client):
    ids = seed(app)

    client.post(
        f"/cart/add/{ids['enduro-helmet-pro']}",
        data={"quantity": 1, "price_cents": 1},  # a malicious client tries to set the price
    )
    html = client.get("/cart").get_data(as_text=True)

    assert "189.00 EUR" in html
    assert "0.01 EUR" not in html


def test_navbar_shows_cart_count(app, client):
    ids = seed(app)

    client.post(f"/cart/add/{ids['riding-gloves-trail']}", data={"quantity": 3})
    html = client.get("/").get_data(as_text=True)

    assert 'text-bg-light">3</span>' in html


def test_cart_post_without_csrf_token_is_rejected():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": True,
        }
    )

    response = app.test_client().post("/cart/add/1", data={"quantity": 1})

    assert response.status_code == 400