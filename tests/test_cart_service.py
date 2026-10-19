from app.extensions import db
from app.models import Product
from app.seed import seed_products
from app.services.cart import (
    add_item,
    cart_item_count,
    cart_total_cents,
    get_cart_lines,
    remove_item,
    set_quantity,
)


def seed(app):
    with app.app_context():
        seed_products()


def get(slug):
    return Product.query.filter_by(slug=slug).one()


def test_add_item_accumulates_quantity(app):
    seed(app)
    with app.test_request_context():
        helmet = get("enduro-helmet-pro")
        add_item(helmet)
        add_item(helmet, 2)

        assert cart_item_count() == 3


def test_quantity_is_capped_by_stock(app):
    seed(app)
    with app.test_request_context():
        assert add_item(get("segway-snarler-at6-l"), 5) == 2  # stock is 2


def test_quantity_is_capped_by_maximum_per_item(app):
    seed(app)
    with app.test_request_context():
        assert add_item(get("riding-gloves-trail"), 50) == 10  # stock is 30


def test_out_of_stock_product_is_not_added(app):
    seed(app)
    with app.test_request_context():
        boots = get("off-road-boots-x")
        boots.stock = 0
        db.session.commit()

        assert add_item(boots) == 0
        assert cart_item_count() == 0


def test_set_quantity_to_zero_removes_item(app):
    seed(app)
    with app.test_request_context():
        helmet = get("enduro-helmet-pro")
        add_item(helmet, 2)

        set_quantity(helmet, 0)

        assert get_cart_lines() == []


def test_remove_item(app):
    seed(app)
    with app.test_request_context():
        helmet = get("enduro-helmet-pro")
        add_item(helmet)

        remove_item(helmet.id)

        assert cart_item_count() == 0


def test_total_uses_database_prices(app):
    seed(app)
    with app.test_request_context():
        add_item(get("riding-gloves-trail"), 2)   # 2 x 49.00
        add_item(get("enduro-helmet-pro"), 1)     # 1 x 189.00

        lines = get_cart_lines()

        assert cart_total_cents(lines) == 28_700