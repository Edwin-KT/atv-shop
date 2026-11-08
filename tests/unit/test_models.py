"""UNIT tests for app/models.py: the classes and the database schema (an in-memory
SQLite database inside an app context; no HTTP).

Rubric: N2.01 database in 3NF (one table per product type, CHECK constraints, the
order total is calculated, not stored); N3.01 classes; N4.01 inheritance
(Product -> VehicleProduct, GearProduct) with polymorphism (get_technical_summary);
N6.01 unit tests."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import GearProduct, Order, OrderItem, Product, User, VehicleProduct


def make_atv(**changes):
    values = dict(name="Test ATV", slug="test-atv", price_cents=1_000_000, stock=2,
                  vehicle_type="atv", engine_cc=1000, horsepower=88, is_street_legal=True)
    return VehicleProduct(**{**values, **changes})


def make_helmet(**changes):
    values = dict(name="Test Helmet", slug="test-helmet", price_cents=25_000, stock=10, gear_size="L")
    return GearProduct(**{**values, **changes})


# --- inheritance and polymorphism (no database needed) ---


@pytest.mark.parametrize(
    "product, summary",
    [
        (make_atv(), "ATV | 1000 cc | 88 hp | street legal"),
        (make_atv(vehicle_type="enduro", is_street_legal=False), "ENDURO | 1000 cc | 88 hp | off-road only"),
        (make_helmet(), "Riding gear | size L"),
    ],
)
def test_each_subclass_describes_itself(product, summary):
    """Same method name, different behaviour per class: polymorphism."""
    assert product.get_technical_summary() == summary


def test_subclasses_inherit_from_product():
    assert isinstance(make_atv(), Product)
    assert isinstance(make_helmet(), Product)
    assert make_atv().image_path == "img/placeholder.svg"  # inherited from Product


def test_the_base_product_has_no_summary_of_its_own():
    with pytest.raises(NotImplementedError):
        Product(name="x", slug="x", price_cents=1).get_technical_summary()


def test_each_product_knows_its_shop_category():
    assert [p.category_key for p in (make_atv(), make_atv(vehicle_type="enduro"), make_helmet())] == [
        "atv", "enduro", "gear"
    ]


@pytest.mark.parametrize(
    "image_filename, path",
    [("ktm-250-exc-f.jpg", "img/products/ktm-250-exc-f.jpg"), (None, "img/placeholder.svg")],
)
def test_image_path_falls_back_to_the_placeholder(image_filename, path):
    assert make_atv(image_filename=image_filename).image_path == path


def test_the_order_total_is_calculated_from_its_items():
    order = Order(items=[OrderItem(unit_price_cents=18_900, quantity=2), OrderItem(unit_price_cents=4_900, quantity=1)])

    assert order.total_cents == 42_700  # 2 x 189.00 + 49.00


def test_prices_are_shown_in_euro_from_cents(app):
    render = app.jinja_env.from_string("{{ cents|eur }}").render

    assert render(cents=1_000_000) == "10,000.00 EUR"
    assert render(cents=5) == "0.05 EUR"


# --- the schema (database) ---


def test_querying_the_base_class_returns_the_right_subclasses(app):
    with app.app_context():
        db.session.add_all([make_atv(), make_helmet()])
        db.session.commit()
        db.session.expire_all()

        products = {p.slug: p for p in Product.query.all()}

        assert isinstance(products["test-atv"], VehicleProduct)
        assert isinstance(products["test-helmet"], GearProduct)


def test_each_product_type_has_its_own_table(app):
    """3NF: columns that only make sense for vehicles are not in the shared table."""
    with app.app_context():
        inspector = inspect(db.engine)
        product_columns = {c["name"] for c in inspector.get_columns("products")}

        assert {"products", "vehicle_details", "gear_details"} <= set(inspector.get_table_names())
        assert "engine_cc" not in product_columns
        assert "gear_size" not in product_columns

        db.session.add_all([make_atv(), make_helmet()])
        db.session.commit()
        counts = [db.session.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                  for t in ("products", "vehicle_details", "gear_details")]
        assert counts == [2, 1, 1]  # the helmet has no (empty) vehicle row


@pytest.mark.parametrize(
    "bad_row",
    [
        lambda: make_helmet(price_cents=-1),
        lambda: make_atv(vehicle_type="boat"),
        lambda: Order(user_id=1, status="shipped"),
        lambda: User(email="x@gmail.com", phone="0712345678", password_hash="h", role="superuser"),
    ],
    ids=["negative price", "unknown vehicle type", "unknown order status", "unknown role"],
)
def test_the_database_rejects_invalid_values(app, bad_row):
    """CHECK constraints: even a bug in the code cannot store these values."""
    with app.app_context():
        db.session.add(bad_row())
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
