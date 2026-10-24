from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.exceptions import OutOfStockError, PaymentError
from app.extensions import db, limiter
from app.models import Order, SecureDocument
from app.models.order import STATUS_PAID
from app.money import format_price
from app.services.audit import record_event
from app.services.cart import cart_total_cents, clear_cart, get_cart_lines
from app.services.orders import cancel_order, confirm_payment, create_order, start_payment

bp = Blueprint("checkout", __name__)


def _gateway():
    return current_app.extensions["payment_gateway"]


def _own_order_or_404(order_id: int) -> Order:
    order = db.session.get(Order, order_id)
    if order is None or order.user_id != current_user.id:
        abort(404)
    return order


def _review_context(lines):
    documents = (
        SecureDocument.query.filter_by(user_id=current_user.id)
        .order_by(SecureDocument.created_at.desc())
        .all()
    )
    return {
        "lines": lines,
        "total_display": format_price(cart_total_cents(lines)),
        "has_vehicle": any(line.product.product_type == "vehicle" for line in lines),
        "documents": documents,
    }


@bp.route("/checkout", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per minute", methods=["POST"])
def start():
    lines = get_cart_lines()
    if not lines:
        flash("Your cart is empty.", "info")
        return redirect(url_for("cart.view_cart"))

    context = _review_context(lines)
    if request.method == "GET":
        return render_template("checkout/review.html", errors=[], **context)

    document_id = None
    chosen = request.form.get("document_id", type=int)
    if chosen:  # optional: only validated when the customer picked one
        document = db.session.get(SecureDocument, chosen)
        if document is None or document.user_id != current_user.id:
            errors = ["The selected document is not valid."]
            return render_template("checkout/review.html", errors=errors, **context), 400
        document_id = document.id

    try:
        order = create_order(current_user.id, lines, document_id)
    except OutOfStockError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("cart.view_cart"))

    success_url = (
        url_for("checkout.success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = url_for("checkout.cancelled", order_id=order.id, _external=True)
    try:
        session = start_payment(order, _gateway(), success_url, cancel_url)
    except PaymentError as exc:
        record_event("payment_failed", user_id=current_user.id, details=str(exc)[:200])
        flash("The payment service is unavailable. Your order was not placed.", "danger")
        return redirect(url_for("cart.view_cart"))

    record_event("order_created", user_id=current_user.id, details=f"order_id={order.id}")
    return redirect(session.url, code=303)


@bp.get("/checkout/success")
@login_required
def success():
    session_id = request.args.get("session_id", "")
    order = None
    if session_id:
        order = Order.query.filter_by(
            stripe_session_id=session_id, user_id=current_user.id
        ).first()
    if order is None:
        abort(404)

    was_paid = order.status == STATUS_PAID
    try:
        paid = confirm_payment(order, _gateway())
    except PaymentError as exc:
        record_event("payment_check_failed", user_id=current_user.id, details=str(exc)[:200])
        flash("We could not verify the payment yet. Check your orders in a minute.", "warning")
        return redirect(url_for("checkout.orders"))

    if paid:
        clear_cart()
        if not was_paid:
            record_event("order_paid", user_id=current_user.id, details=f"order_id={order.id}")
    return render_template("checkout/success.html", order=order, paid=paid)


@bp.get("/checkout/cancel/<int:order_id>")
@login_required
def cancelled(order_id):
    order = _own_order_or_404(order_id)
    return render_template("checkout/cancelled.html", order=order)


@bp.get("/orders")
@login_required
def orders():
    user_orders = (
        Order.query.filter_by(user_id=current_user.id).order_by(Order.id.desc()).all()
    )
    return render_template("checkout/orders.html", orders=user_orders)


@bp.post("/orders/<int:order_id>/cancel")
@login_required
def cancel(order_id):
    order = _own_order_or_404(order_id)

    try:
        if confirm_payment(order, _gateway()):
            flash("This order was already paid, so it cannot be cancelled.", "warning")
            return redirect(url_for("checkout.orders"))
    except PaymentError:
        flash("We could not check the payment status. Try again in a minute.", "warning")
        return redirect(url_for("checkout.orders"))

    if cancel_order(order, _gateway()):
        record_event("order_cancelled", user_id=current_user.id, details=f"order_id={order.id}")
        flash("Order cancelled. The items are back in stock.", "info")
    return redirect(url_for("checkout.orders"))