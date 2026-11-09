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
from app.extensions import db
from app.models import STATUS_PENDING, Order
from app.activity_log import log_event
from app.services.cart import clear_cart, get_cart_lines
from app.services.orders import cancel_order, confirm_payment, create_order, start_payment

bp = Blueprint("checkout", __name__)


def _gateway():
    return current_app.extensions["payment_gateway"]


def _own_order_or_404(order_id: int) -> Order:
    order = db.session.get(Order, order_id)
    if order is None or order.user_id != current_user.id:
        abort(404)
    return order


@bp.route("/checkout", methods=["GET", "POST"])
@login_required
def start():
    # Only reachable by GET when the login page sends the customer back here.
    if request.method == "GET":
        return redirect(url_for("cart.view_cart"))

    lines = get_cart_lines()
    if not lines:
        flash("Your cart is empty.", "info")
        return redirect(url_for("cart.view_cart"))

    try:
        order = create_order(current_user.id, lines)
    except OutOfStockError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("cart.view_cart"))

    success_url = (
        url_for("checkout.success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = url_for("checkout.cancelled", order_id=order.id, _external=True)
    try:
        payment_url = start_payment(order, _gateway(), success_url, cancel_url)
    except PaymentError as exc:
        log_event("payment_failed", details=str(exc)[:200])
        flash("The payment service is unavailable. Your order was not placed.", "danger")
        return redirect(url_for("cart.view_cart"))

    log_event("order_created", details=f"order_id={order.id}")
    return redirect(payment_url, code=303)  # to Stripe's payment page


@bp.get("/checkout/success")
@login_required
def success():
    # Stripe adds ?session_id=... to the success URL. Only the owner's order matches;
    # the ORM sends the value as a bound parameter, so it is never run as SQL.
    session_id = request.args.get("session_id", "")
    order = Order.query.filter_by(stripe_session_id=session_id, user_id=current_user.id).first()
    if order is None:
        abort(404)

    was_paid = order.is_paid
    try:
        paid = confirm_payment(order, _gateway())
    except PaymentError as exc:
        log_event("payment_check_failed", details=str(exc)[:200])
        flash("We could not verify the payment yet. Check your orders in a minute.", "warning")
        return redirect(url_for("checkout.orders"))

    if paid:
        clear_cart()
        if not was_paid:
            log_event("order_paid", details=f"order_id={order.id}")
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
    # A customer may pay and close the Stripe tab before the success page loads:
    # ask Stripe again about the orders that still wait for a payment.
    for order in user_orders:
        if order.status != STATUS_PENDING:
            continue
        try:
            if confirm_payment(order, _gateway()):
                log_event("order_paid", details=f"order_id={order.id}")
        except PaymentError as exc:
            log_event("payment_check_failed", details=str(exc)[:200])
            flash("We could not reach the payment service, so a status may be out of date.", "warning")
            break  # Stripe is down: do not wait for it once per order
    return render_template("checkout/orders.html", orders=user_orders)


@bp.post("/orders/<int:order_id>/cancel")
@login_required
def cancel(order_id):
    order = _own_order_or_404(order_id)

    try:
        if confirm_payment(order, _gateway()):
            flash("This order was already paid, so it cannot be cancelled.", "warning")
            return redirect(url_for("checkout.orders"))
        cancelled = cancel_order(order, _gateway())  # closes the Stripe page first
    except PaymentError as exc:
        # Stripe could not be asked, or its page could not be closed: the customer
        # might still pay there, so the order stays as it is.
        log_event("order_cancel_failed", details=str(exc)[:200])
        flash("We could not reach the payment service, so the order was not cancelled. "
              "Try again in a minute.", "warning")
        return redirect(url_for("checkout.orders"))

    if cancelled:
        log_event("order_cancelled", details=f"order_id={order.id}")
        flash("Order cancelled. The items are back in stock.", "info")
    return redirect(url_for("checkout.orders"))