from datetime import datetime, timezone

from app.extensions import db
from app.money import format_price

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
    document_id = db.Column(db.Integer, db.ForeignKey("secure_documents.id"))  # vehicle papers
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    stripe_session_id = db.Column(db.String(255), unique=True)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    paid_at = db.Column(db.DateTime(timezone=True))

    items = db.relationship(
        "OrderItem", cascade="all, delete-orphan", order_by="OrderItem.id"
    )

    @property
    def total_cents(self) -> int:
        """Derived from the items, never stored (keeps the schema in 3NF)."""
        return sum(item.line_total_cents for item in self.items)

    @property
    def total_display(self) -> str:
        return format_price(self.total_cents)


class OrderItem(db.Model):
    __tablename__ = "order_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        db.CheckConstraint("unit_price_cents >= 0", name="ck_order_items_price_non_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    # The price at the moment of purchase: a fact about this sale, not a copy of products.price.
    unit_price_cents = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    product = db.relationship("Product")

    @property
    def line_total_cents(self) -> int:
        return self.unit_price_cents * self.quantity

    @property
    def unit_price_display(self) -> str:
        return format_price(self.unit_price_cents)

    @property
    def line_total_display(self) -> str:
        return format_price(self.line_total_cents)