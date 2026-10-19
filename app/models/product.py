from app.extensions import db
from app.money import format_price


class Product(db.Model):
    """Base class. All products share one table (single table inheritance);
    the `product_type` column tells SQLAlchemy which subclass a row belongs to."""

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    product_type = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    price_cents = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)

    __mapper_args__ = {
        "polymorphic_on": product_type,
        "polymorphic_identity": "product",
    }

    @property
    def price_display(self) -> str:
        return format_price(self.price_cents)

    def get_technical_summary(self) -> str:
        """Each subclass describes itself differently (polymorphism)."""
        raise NotImplementedError("Subclasses must implement get_technical_summary()")


class VehicleProduct(Product):
    """ATVs and enduro motorcycles."""

    # No __tablename__: the columns below are added to the `products` table.
    # They must be nullable, because gear rows leave them empty.
    engine_cc = db.Column(db.Integer)
    horsepower = db.Column(db.Integer)
    is_street_legal = db.Column(db.Boolean)
    vehicle_type = db.Column(db.String(20))  # "atv" or "enduro"

    __mapper_args__ = {"polymorphic_identity": "vehicle"}

    def get_technical_summary(self) -> str:
        legal = "street legal" if self.is_street_legal else "off-road only"
        return (
            f"{self.vehicle_type.upper()} | {self.engine_cc} cc | "
            f"{self.horsepower} hp | {legal}"
        )


class GearProduct(Product):
    """Helmets, boots, gloves and other riding gear."""

    gear_size = db.Column(db.String(10))

    __mapper_args__ = {"polymorphic_identity": "gear"}

    def get_technical_summary(self) -> str:
        return f"Riding gear | size {self.gear_size}"