"""The database tables (the "M" in MVC), all in one place.

Tables: users, products (+ vehicle_details, gear_details), orders, order_items,
secure_documents. The schema is in 3NF: every column depends only on its own
table's key, and nothing that can be calculated (an order total) is stored."""

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


def _now():
    return datetime.now(timezone.utc)


# ---------- users ----------

ROLE_CUSTOMER = "customer"
ROLE_ADMIN = "admin"


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("role IN ('customer', 'admin')", name="ck_users_role_allowed"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(10), nullable=False)  # exactly 10 digits, checked in validators.py
    password_hash = db.Column(db.String(255), nullable=False)  # never the password itself
    role = db.Column(db.String(20), nullable=False, default=ROLE_CUSTOMER)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)  # salted hash

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id: str):
    """Flask-Login calls this on every request to turn the id stored
    in the session cookie back into a User object."""
    return db.session.get(User, int(user_id))


# ---------- products: one base class, two subclasses (inheritance) ----------


class Product(db.Model):
    """Base class: the columns every product has.

    Joined-table inheritance: each subclass keeps its own columns in its own table,
    whose primary key is also a foreign key to products.id. So there are no columns
    that would stay NULL for one kind of product (3NF)."""

    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("price_cents >= 0", name="ck_products_price_non_negative"),
        db.CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_type = db.Column(db.String(20), nullable=False)  # "vehicle" or "gear"
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False)  # used in the URL
    description = db.Column(db.Text, nullable=False, default="")
    price_cents = db.Column(db.Integer, nullable=False)  # whole cents: no rounding errors
    stock = db.Column(db.Integer, nullable=False, default=0)
    image_filename = db.Column(db.String(255))  # a file in static/img/products/ (optional)

    # SQLAlchemy reads product_type to build a VehicleProduct or a GearProduct.
    __mapper_args__ = {"polymorphic_on": product_type, "polymorphic_identity": "product"}

    @property
    def image_path(self) -> str:
        """Path inside static/ for url_for("static", filename=...)."""
        if self.image_filename:
            return f"img/products/{self.image_filename}"
        return "img/placeholder.svg"

    def get_technical_summary(self) -> str:
        """Each subclass describes itself differently (polymorphism)."""
        raise NotImplementedError("Subclasses must implement get_technical_summary()")

    @property
    def category_key(self) -> str:
        """The shop category this product is listed in ("atv", "enduro" or "gear")."""
        raise NotImplementedError("Subclasses must implement category_key")


class VehicleProduct(Product):
    """ATVs and enduro motorcycles."""

    __tablename__ = "vehicle_details"
    __table_args__ = (
        db.CheckConstraint("engine_cc > 0", name="ck_vehicle_engine_positive"),
        db.CheckConstraint("horsepower > 0", name="ck_vehicle_horsepower_positive"),
        db.CheckConstraint("vehicle_type IN ('atv', 'enduro')", name="ck_vehicle_type_allowed"),
    )

    id = db.Column(db.Integer, db.ForeignKey("products.id"), primary_key=True)
    engine_cc = db.Column(db.Integer, nullable=False)
    horsepower = db.Column(db.Integer, nullable=False)
    is_street_legal = db.Column(db.Boolean, nullable=False)
    vehicle_type = db.Column(db.String(20), nullable=False)  # "atv" or "enduro"

    __mapper_args__ = {"polymorphic_identity": "vehicle"}

    def get_technical_summary(self) -> str:
        legal = "street legal" if self.is_street_legal else "off-road only"
        return f"{self.vehicle_type.upper()} | {self.engine_cc} cc | {self.horsepower} hp | {legal}"

    @property
    def category_key(self) -> str:
        return self.vehicle_type


class GearProduct(Product):
    """Helmets, boots, gloves and other riding gear."""

    __tablename__ = "gear_details"

    id = db.Column(db.Integer, db.ForeignKey("products.id"), primary_key=True)
    gear_size = db.Column(db.String(10), nullable=False)

    __mapper_args__ = {"polymorphic_identity": "gear"}

    def get_technical_summary(self) -> str:
        return f"Riding gear | size {self.gear_size}"

    @property
    def category_key(self) -> str:
        return "gear"


# ---------- orders ----------

# An order is created "pending" (stock reserved, waiting for Stripe), then becomes
# "paid" when Stripe confirms the payment, or "cancelled" (stock given back).
STATUS_PENDING = "pending"
STATUS_PAID = "paid"
STATUS_CANCELLED = "cancelled"


class Order(db.Model):
    __tablename__ = "orders"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled')", name="ck_orders_status_allowed"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    stripe_session_id = db.Column(db.String(255), unique=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    paid_at = db.Column(db.DateTime(timezone=True))

    items = db.relationship("OrderItem", cascade="all, delete-orphan", order_by="OrderItem.id")
    user = db.relationship("User")  # no new column: uses user_id

    @property
    def is_paid(self) -> bool:
        return self.status == STATUS_PAID

    @property
    def total_cents(self) -> int:
        """Calculated from the items, never stored (keeps the schema in 3NF)."""
        return sum(item.line_total_cents for item in self.items)


class OrderItem(db.Model):
    __tablename__ = "order_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        db.CheckConstraint("unit_price_cents >= 0", name="ck_order_items_price_non_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    # The price at the moment of purchase: a fact about this sale, not a copy of
    # products.price_cents (which may change later).
    unit_price_cents = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    product = db.relationship("Product")

    @property
    def line_total_cents(self) -> int:
        return self.unit_price_cents * self.quantity


# ---------- uploaded documents ----------


class SecureDocument(db.Model):
    """Data about an uploaded PDF. The file itself is in private_uploads/."""

    __tablename__ = "secure_documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)  # only shown to the user
    stored_filename = db.Column(db.String(64), unique=True, nullable=False)  # random name on disk
    size_bytes = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
