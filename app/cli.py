"""Command line tools: `flask --app wsgi seed-products` and `flask --app wsgi create-admin`."""

import click

from app.extensions import db
from app.models import ROLE_ADMIN, GearProduct, Product, User, VehicleProduct
from app.validators import is_valid_email, is_valid_password, is_valid_phone


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


def create_admin(email: str, phone: str, password: str) -> User:
    """Create an admin account. Raises ValueError with a readable message.
    Admins can only be made here, on the server: the register page always makes customers."""
    email = email.strip().lower()
    if not is_valid_email(email):
        raise ValueError("Invalid email address.")
    if not is_valid_phone(phone):
        raise ValueError("Phone number must have exactly 10 digits.")
    if not is_valid_password(password):
        raise ValueError("Password must have at least 8 characters.")
    if User.query.filter_by(email=email).first():
        raise ValueError("An account with this email already exists.")

    admin = User(email=email, phone=phone, role=ROLE_ADMIN)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return admin


def register_commands(app):
    @app.cli.command("seed-products")
    def seed_products_command():
        """Insert the sample products into the database."""
        click.echo(f"Added {seed_products()} product(s).")

    @app.cli.command("create-admin")
    @click.argument("email")
    @click.argument("phone")
    @click.password_option()
    def create_admin_command(email, phone, password):
        """Create an admin user. The password is asked twice, without showing it."""
        try:
            admin = create_admin(email, phone, password)
        except ValueError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"Admin created: {admin.email}")
