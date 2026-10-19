import pytest

from app.extensions import db
from app.models import GearProduct, Product, VehicleProduct


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