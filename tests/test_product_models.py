import pytest

from app.extensions import db
from app.models import GearProduct, Product, VehicleProduct
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError


def make_atv():
    return VehicleProduct(
        name="Test ATV", slug="test-atv", price_cents=1_000_000, stock=2,
        vehicle_type="atv", engine_cc=1000, horsepower=88, is_street_legal=True,
    )


def make_helmet():
    return GearProduct(
        name="Test Helmet", slug="test-helmet", price_cents=25_000, stock=10,
        gear_size="L",
    )


# --- unit tests (no database) ---

def test_vehicle_summary():
    assert make_atv().get_technical_summary() == "ATV | 1000 cc | 88 hp | street legal"


def test_gear_summary():
    assert make_helmet().get_technical_summary() == "Riding gear | size L"


def test_subclasses_inherit_from_product():
    assert isinstance(make_atv(), Product)
    assert isinstance(make_helmet(), Product)


def test_base_product_has_no_summary():
    with pytest.raises(NotImplementedError):
        Product(name="x", slug="x", price_cents=1).get_technical_summary()


def test_price_display():
    assert make_atv().price_display == "10,000.00 EUR"


# --- integration test (database) ---

def test_querying_base_class_returns_correct_subclasses(app):
    with app.app_context():
        db.session.add_all([make_atv(), make_helmet()])
        db.session.commit()
        db.session.expire_all()

        products = {p.slug: p for p in Product.query.all()}

        assert isinstance(products["test-atv"], VehicleProduct)
        assert isinstance(products["test-helmet"], GearProduct)
        assert products["test-atv"].product_type == "vehicle"



# --- schema tests (3NF) ---

def test_each_type_has_its_own_table(app):
    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        product_columns = {c["name"] for c in inspector.get_columns("products")}

        assert {"products", "vehicle_details", "gear_details"} <= tables
        # type-specific columns must not live in the shared table
        assert "engine_cc" not in product_columns
        assert "gear_size" not in product_columns


def test_gear_does_not_create_a_vehicle_row(app):
    with app.app_context():
        db.session.add_all([make_atv(), make_helmet()])
        db.session.commit()

        vehicles = db.session.execute(text("SELECT COUNT(*) FROM vehicle_details")).scalar()
        gear = db.session.execute(text("SELECT COUNT(*) FROM gear_details")).scalar()

        assert (vehicles, gear) == (1, 1)


def test_database_rejects_negative_price(app):
    with app.app_context():
        helmet = make_helmet()
        helmet.price_cents = -1
        db.session.add(helmet)

        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_database_rejects_unknown_vehicle_type(app):
    with app.app_context():
        vehicle = make_atv()
        vehicle.vehicle_type = "boat"
        db.session.add(vehicle)

        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()