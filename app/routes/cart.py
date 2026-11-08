from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Product
from app.services.cart import add_item, cart_total_cents, get_cart_lines, set_quantity

bp = Blueprint("cart", __name__)


@bp.get("/cart")
def view_cart():
    lines = get_cart_lines()
    return render_template("cart.html", lines=lines, total_cents=cart_total_cents(lines))


@bp.post("/cart/add/<int:product_id>")
def add(product_id):
    product = db.get_or_404(Product, product_id)
    quantity = request.form.get("quantity", default=1, type=int)

    if add_item(product, quantity) == 0:
        flash("This product is out of stock.", "warning")
        return redirect(url_for("main.product_detail", slug=product.slug))

    flash(f"{product.name} added to cart.", "success")
    return redirect(url_for("cart.view_cart"))


@bp.post("/cart/update/<int:product_id>")
def update(product_id):
    product = db.get_or_404(Product, product_id)
    quantity = request.form.get("quantity", type=int)

    if quantity is None:
        flash("Invalid quantity.", "danger")
    elif set_quantity(product, quantity) == 0:
        flash("Item removed.", "info")
    return redirect(url_for("cart.view_cart"))