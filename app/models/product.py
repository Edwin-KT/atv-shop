from app.extensions import db
from app.money import format_price


class Product(db.Model):
    """Base class: columns shared by every product.

    Joined table inheritance: each subclass stores its own columns in a
    separate table whose primary key is also a foreign key to products.id.
    This keeps the schema in 3NF (no columns that are NULL for some types)."""

    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("price_cents >= 0", name="ck_products_price_non_negative"),
        db.CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_type = db.Column(db.String(20), nullable=False)  # discriminator
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    price_cents = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)

    __mapper_args__ = {
        "polymorphic_on": product_type,
        "polymorphic_identity": "product",
        # Load subclass columns in the same query (avoids one extra query per row).
        "with_polymorphic": "*",
    }

    @property
    def price_display(self) -> str:
        return format_price(self.price_cents)

    def get_technical_summary(self) -> str:
        """Each subclass describes itself differently (polymorphism)."""
        raise NotImplementedError("Subclasses must implement get_technical_summary()")


class VehicleProduct(Product):
    """ATVs and enduro motorcycles."""

    __tablename__ = "vehicle_details"
    __table_args__ = (
        db.CheckConstraint("engine_cc > 0", name="ck_vehicle_engine_positive"),
        db.CheckConstraint("horsepower > 0", name="ck_vehicle_horsepower_positive"),
        db.CheckConstraint(
            "vehicle_type IN ('atv', 'enduro')", name="ck_vehicle_type_allowed"
        ),
    )

    id = db.Column(db.Integer, db.ForeignKey("products.id"), primary_key=True)
    engine_cc = db.Column(db.Integer, nullable=False)
    horsepower = db.Column(db.Integer, nullable=False)
    is_street_legal = db.Column(db.Boolean, nullable=False)
    vehicle_type = db.Column(db.String(20), nullable=False)  # "atv" or "enduro"

    __mapper_args__ = {"polymorphic_identity": "vehicle"}

    def get_technical_summary(self) -> str:
        legal = "street legal" if self.is_street_legal else "off-road only"
        return (
            f"{self.vehicle_type.upper()} | {self.engine_cc} cc | "
            f"{self.horsepower} hp | {legal}"
        )


class GearProduct(Product):
    """Helmets, boots, gloves and other riding gear."""

    __tablename__ = "gear_details"

    id = db.Column(db.Integer, db.ForeignKey("products.id"), primary_key=True)
    gear_size = db.Column(db.String(10), nullable=False)

    __mapper_args__ = {"polymorphic_identity": "gear"}

    def get_technical_summary(self) -> str:
        return f"Riding gear | size {self.gear_size}"