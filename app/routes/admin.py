from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.models import AuditLog, Product
from app.security import check_admin_access
from app.services.audit import record_event
from app.services.products import (
    PRODUCT_CLASSES,
    create_product,
    update_product,
    validate_product_form,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")

# Runs before EVERY route of this blueprint, including routes added later.
bp.before_request(check_admin_access)


def _values_from_product(product: Product) -> dict:
    """Prefill values for the edit form."""
    values = {
        "name": product.name,
        "description": product.description,
        "price": f"{product.price_cents / 100:.2f}",
        "stock": str(product.stock),
        "image_filename": product.image_filename or "",
    }
    if product.product_type == "vehicle":
        values.update(
            vehicle_type=product.vehicle_type,
            engine_cc=str(product.engine_cc),
            horsepower=str(product.horsepower),
            is_street_legal="on" if product.is_street_legal else "",
        )
    else:
        values["gear_size"] = product.gear_size
    return values


@bp.get("/")
def dashboard():
    products = Product.query.order_by(Product.name).all()
    return render_template("admin/dashboard.html", products=products)


@bp.route("/products/new", methods=["GET", "POST"])
def new_product():
    product_type = request.args.get("type", "")
    if product_type not in PRODUCT_CLASSES:
        abort(404)

    action_url = url_for("admin.new_product", type=product_type)
    if request.method == "GET":
        return render_template(
            "admin/product_form.html", product=None, product_type=product_type,
            values={}, errors=[], action_url=action_url,
        )

    clean, errors = validate_product_form(request.form, product_type)
    if errors:
        return render_template(
            "admin/product_form.html", product=None, product_type=product_type,
            values=request.form, errors=errors, action_url=action_url,
        ), 400

    product = create_product(product_type, clean)
    record_event("product_created", user_id=current_user.id, details=f"product_id={product.id}")
    flash("Product created.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    product = db.get_or_404(Product, product_id)
    action_url = url_for("admin.edit_product", product_id=product.id)

    if request.method == "GET":
        return render_template(
            "admin/product_form.html", product=product, product_type=product.product_type,
            values=_values_from_product(product), errors=[], action_url=action_url,
        )

    # The type comes from the stored product, never from the form.
    clean, errors = validate_product_form(request.form, product.product_type)
    if errors:
        return render_template(
            "admin/product_form.html", product=product, product_type=product.product_type,
            values=request.form, errors=errors, action_url=action_url,
        ), 400

    update_product(product, clean)
    record_event("product_updated", user_id=current_user.id, details=f"product_id={product.id}")
    flash("Product updated.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/products/<int:product_id>/delete")
def delete_product(product_id):
    product = db.get_or_404(Product, product_id)
    deleted_id = product.id
    db.session.delete(product)
    db.session.commit()

    record_event("product_deleted", user_id=current_user.id, details=f"product_id={deleted_id}")
    flash("Product deleted.", "info")
    return redirect(url_for("admin.dashboard"))


@bp.get("/logs")
def audit_log():
    entries = AuditLog.query.order_by(AuditLog.id.desc()).limit(100).all()
    return render_template("admin/audit_log.html", entries=entries)