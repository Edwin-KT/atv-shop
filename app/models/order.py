from datetime import datetime, timezone

from app.extensions import db
from app.money import format_price

STATUS_PENDING = "pending"
STATUS_PAID = "paid"
STATUS_PROCESSING = "processing"
STATUS_SHIPPED = "shipped"
STATUS_DELIVERED = "delivered"
STATUS_CANCELLED = "cancelled"

ALL_STATUSES = (
    STATUS_PENDING, STATUS_PAID, STATUS_PROCESSING,
    STATUS_SHIPPED, STATUS_DELIVERED, STATUS_CANCELLED,
)
# Every status an order can have once Stripe confirmed the payment.
PAID_STATUSES = (STATUS_PAID, STATUS_PROCESSING, STATUS_SHIPPED, STATUS_DELIVERED)
# Forward-only fulfilment: each status has at most one next step.
NEXT_STATUS = {
    STATUS_PAID: STATUS_PROCESSING,
    STATUS_PROCESSING: STATUS_SHIPPED,
    STATUS_SHIPPED: STATUS_DELIVERED,
}
STATUS_LABELS = {
    STATUS_PENDING: "Awaiting payment",
    STATUS_PAID: "Paid",
    STATUS_PROCESSING: "Processing",
    STATUS_SHIPPED: "Shipped",
    STATUS_DELIVERED: "Delivered",
    STATUS_CANCELLED: "Cancelled",
}


class Order(db.Model):
    __tablename__ = "orders"
    __table_args__ = (
        db.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in ALL_STATUSES) + ")",
            name="ck_orders_status_allowed",
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
    user = db.relationship("User")  # no new column: uses the existing user_id

    @property
    def is_paid(self) -> bool:
        return self.status in PAID_STATUSES

    @property
    def next_status(self) -> str | None:
        return NEXT_STATUS.get(self.status)

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

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