"""Small helpers shared by the tests (imported as `from helpers import ...`)."""

from app.cli import create_admin, seed_products
from app.models import Product

PASSWORD = "parola-sigura-123"
ADMIN_EMAIL = "boss@gmail.com"
ADMIN_PASSWORD = "parola-admin-123"


def seed(app) -> dict:
    """Insert the 6 sample products; return {slug: id}."""
    with app.app_context():
        seed_products()
        return {product.slug: product.id for product in Product.query.all()}


def register_and_login(client, email="ana@gmail.com"):
    """A customer account, created and logged in through the real forms."""
    client.post("/register", data={"email": email, "phone": "0712345678", "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client


def admin_client(app):
    """A new test client logged in as an admin (admins are only made from the CLI)."""
    with app.app_context():
        create_admin(ADMIN_EMAIL, "0711111111", ADMIN_PASSWORD)
    client = app.test_client()
    client.post("/login", data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    return client


def page(client, url) -> str:
    return client.get(url).get_data(as_text=True)
