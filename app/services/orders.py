from datetime import datetime, timezone

from sqlalchemy import update

from app.exceptions import EmptyCartError, OutOfStockError, PaymentError
from app.extensions import db
from app.models import Order, OrderItem, Product
from app.models.order import NEXT_STATUS, STATUS_CANCELLED, STATUS_PAID, STATUS_PENDING
from app.services.cart import CartLine
from app.services.payment_interface import PaymentGateway, PaymentItem

_products = Product.__table__
_orders = Order.__table__


def _reserve_stock(product_id: int, product_name: str, quantity: int) -> None:
    """Atomic: the UPDATE only matches if enough stock remains, so two buyers
    can never both take the last item."""
    result = db.session.execute(
        update(_products)
        .where(_products.c.id == product_id, _products.c.stock >= quantity)
        .values(stock=_products.c.stock - quantity)
    )
    if result.rowcount != 1:
        raise OutOfStockError(product_name)


def create_order(user_id: int, lines: list[CartLine], document_id: int | None) -> Order:
    """Create a pending order and reserve its stock. All or nothing."""
    if not lines:
        raise EmptyCartError("Your cart is empty.")

    order = Order(user_id=user_id, document_id=document_id, status=STATUS_PENDING)
    try:
        for line in lines:
            product = line.product
            _reserve_stock(product.id, product.name, line.quantity)
            order.items.append(
                OrderItem(
                    product_id=product.id,
                    unit_price_cents=product.price_cents,  # always from the database
                    quantity=line.quantity,
                )
            )
        db.session.add(order)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return order


def start_payment(order: Order, gateway: PaymentGateway, success_url: str, cancel_url: str):
    """Open the hosted payment page. If the provider fails, release the stock."""
    items = [
        PaymentItem(item.product.name, item.unit_price_cents, item.quantity)
        for item in order.items
    ]
    try:
        session = gateway.create_checkout_session(
            str(order.id), items, success_url, cancel_url
        )
    except PaymentError:
        cancel_order(order)
        raise

    order.stripe_session_id = session.session_id
    db.session.commit()
    return session


def confirm_payment(order: Order, gateway: PaymentGateway) -> bool:
    """Ask the provider if the order was paid; mark it paid when it was.

    Safe to call repeatedly. Raises PaymentError if the provider cannot be asked
    or answers about a different order."""
    if order.is_paid:  # paid, processing, shipped or delivered
        return True
    if order.status != STATUS_PENDING or not order.stripe_session_id:
        return False

    result = gateway.get_payment_result(order.stripe_session_id)
    if result.order_reference != str(order.id):
        raise PaymentError("The payment does not belong to this order.")
    if not result.paid:
        return False

    order.status = STATUS_PAID
    order.paid_at = datetime.now(timezone.utc)
    db.session.commit()
    return True


def cancel_order(order: Order, gateway: PaymentGateway | None = None) -> bool:
    """Cancel a pending order and put its items back in stock. Returns False
    if there was nothing to cancel, so stock is never restored twice."""
    if order.status != STATUS_PENDING:
        return False

    if gateway is not None and order.stripe_session_id:
        try:
            gateway.cancel_checkout_session(order.stripe_session_id)
        except PaymentError:
            pass  # the session expires on its own; the local order is cancelled anyway

    for item in order.items:
        db.session.execute(
            update(_products)
            .where(_products.c.id == item.product_id)
            .values(stock=_products.c.stock + item.quantity)
        )
    order.status = STATUS_CANCELLED
    db.session.commit()
    return True


def advance_order_status(order_id: int, expected_status: str) -> str | None:
    """Move an order exactly one step forward (paid -> processing -> shipped -> delivered).

    `expected_status` is the status the admin saw. The UPDATE only matches if the
    order still has it, so a double click or two admins at once can never skip a
    step. Returns the new status, or None if nothing was changed. Stock is not
    touched: it was reserved at checkout."""
    new_status = NEXT_STATUS.get(expected_status)
    if new_status is None:  # pending, cancelled, delivered or an unknown value
        return None

    result = db.session.execute(
        update(_orders)
        .where(_orders.c.id == order_id, _orders.c.status == expected_status)
        .values(status=new_status)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return None
    db.session.commit()
    return new_status
