from app.extensions import db
from app.models import GearProduct, Product, VehicleProduct

SAMPLE_PRODUCTS = [
    VehicleProduct(
        name="CFMOTO CFORCE 1000 Overland",
        slug="cfmoto-cforce-1000-overland",
        description="Powerful two-seat ATV for trails and heavy-duty work.",
        price_cents=1_299_900, stock=3,
        vehicle_type="atv", engine_cc=963, horsepower=88, is_street_legal=True,
    ),
    VehicleProduct(
        name="Kayo TT250 Enduro",
        slug="kayo-tt250-enduro",
        description="Lightweight enduro bike for forest trails and hard enduro.",
        price_cents=459_900, stock=5,
        vehicle_type="enduro", engine_cc=249, horsepower=24, is_street_legal=False,
    ),
    VehicleProduct(
        name="Segway Snarler AT6 L",
        slug="segway-snarler-at6-l",
        description="Road-legal utility ATV with a comfortable ride.",
        price_cents=899_900, stock=2,
        vehicle_type="atv", engine_cc=570, horsepower=41, is_street_legal=True,
    ),
    GearProduct(
        name="Enduro Helmet Pro",
        slug="enduro-helmet-pro",
        description="Lightweight composite helmet with extended peak.",
        price_cents=18_900, stock=20, gear_size="L",
    ),
    GearProduct(
        name="Off-Road Boots X",
        slug="off-road-boots-x",
        description="Reinforced boots with ankle protection.",
        price_cents=21_900, stock=12, gear_size="43",
    ),
    GearProduct(
        name="Riding Gloves Trail",
        slug="riding-gloves-trail",
        description="Breathable gloves with knuckle protection.",
        price_cents=4_900, stock=30, gear_size="M",
    ),
]


def seed_products() -> int:
    """Insert sample products that do not exist yet. Returns how many were added."""
    added = 0
    for product in SAMPLE_PRODUCTS:
        if not Product.query.filter_by(slug=product.slug).first():
            db.session.add(product)
            added += 1
    db.session.commit()
    return added