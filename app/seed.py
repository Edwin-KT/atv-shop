from app.extensions import db
from app.models import GearProduct, Product, VehicleProduct


def build_sample_products() -> list[Product]:
    """Create fresh product objects on every call.

    A module-level list would be shared between app instances, and objects
    from a closed session cannot be added to a new one."""
    return [
        VehicleProduct(
            name="CFMOTO CFORCE 1000 Overland",
            slug="cfmoto-cforce-1000-overland",
            description="Powerful two-seat ATV for trails and heavy-duty work.",
            price_cents=1_299_900, stock=3, image_filename="cfmoto-cforce-1000-overland.png",
            vehicle_type="atv", engine_cc=963, horsepower=88, is_street_legal=True,
        ),
        VehicleProduct(
            name="KTM 250 EXC-F",
            slug="ktm-250-exc-f",
            description="Competition-ready enduro bike for forest trails and hard enduro.",
            price_cents=1_099_900, stock=5, image_filename="ktm-250-exc-f.jpg",
            vehicle_type="enduro", engine_cc=249, horsepower=40, is_street_legal=False,
        ),
        VehicleProduct(
            name="Segway Snarler AT6 L",
            slug="segway-snarler-at6-l",
            description="Road-legal utility ATV with a comfortable ride.",
            price_cents=899_900, stock=2, image_filename="segway-snarler-at6-l.jpg",
            vehicle_type="atv", engine_cc=570, horsepower=41, is_street_legal=True,
        ),
        GearProduct(
            name="Enduro Helmet Pro",
            slug="enduro-helmet-pro",
            description="Lightweight composite helmet with extended peak.",
            price_cents=18_900, stock=20, image_filename="enduro-helmet-pro.jpg",
            gear_size="L",
        ),
        GearProduct(
            name="Off-Road Boots X",
            slug="off-road-boots-x",
            description="Reinforced boots with ankle protection.",
            price_cents=21_900, stock=12, image_filename="off-road-boots-x.jpg",
            gear_size="43",
        ),
        GearProduct(
            name="Riding Gloves Trail",
            slug="riding-gloves-trail",
            description="Breathable gloves with knuckle protection.",
            price_cents=4_900, stock=30, image_filename="riding-gloves-trail.jpg",
            gear_size="M",
        ),
    ]


def seed_products() -> int:
    """Insert sample products that do not exist yet. Returns how many were added."""
    added = 0
    for product in build_sample_products():
        if not Product.query.filter_by(slug=product.slug).first():
            db.session.add(product)
            added += 1
    db.session.commit()
    return added