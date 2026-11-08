"""INTEGRATION tests: the admin area through the real routes.

Rubric: N2.02 use case "manage products" (create, read, update, delete) and the
read-only orders list; N2.04 tables; N4.01 the right subclass is created for each
product type. Who may enter /admin is tested in test_access_control.py."""

import re

import pytest
from sqlalchemy import text

from app.extensions import db
from app.models import GearProduct, Order, Product, VehicleProduct
from helpers import admin_client, page, register_and_login, seed

VEHICLE_FORM = {
    "name": "Yamaha Raptor 700",
    "description": "Sport ATV",
    "price": "8999.00",
    "stock": "3",
    "image_filename": "yamaha-raptor-700.jpg",
    "vehicle_type": "atv",
    "engine_cc": "686",
    "horsepower": "50",
    "is_street_legal": "on",
}
GEAR_FORM = {"name": "Trail Jacket", "description": "", "price": "129.90", "stock": "10", "gear_size": "L"}


@pytest.fixture()
def admin(app):
    return admin_client(app)


def product_count(app):
    with app.app_context():
        return Product.query.count()


def make_paid_order(app):
    """A customer buys two helmets and pays (through the real routes); returns the helmet's id."""
    ids = seed(app)
    customer = register_and_login(app.test_client())
    customer.post(f"/cart/add/{ids['enduro-helmet-pro']}", data={"quantity": 2})
    customer.post("/checkout")
    with app.app_context():
        session_id = Order.query.one().stripe_session_id
    app.extensions["payment_gateway"].mark_paid(session_id)
    customer.get(f"/checkout/success?session_id={session_id}")
    return ids["enduro-helmet-pro"]


# --- create ---


def test_the_admin_creates_a_vehicle(app, admin):
    response = admin.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    assert response.status_code == 302
    with app.app_context():
        product = Product.query.one()
        assert isinstance(product, VehicleProduct)
        assert product.slug == "yamaha-raptor-700"
        assert product.price_cents == 899_900
        assert product.is_street_legal is True


def test_the_admin_creates_riding_gear(app, admin):
    admin.post("/admin/products/new?type=gear", data=GEAR_FORM)

    with app.app_context():
        product = Product.query.one()
        assert isinstance(product, GearProduct)
        assert product.price_cents == 12_990
        assert product.image_filename is None


def test_a_second_product_with_the_same_name_is_refused(app, admin):
    """The name gives the URL (/product/yamaha-raptor-700), so it must be unique."""
    admin.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    response = admin.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    assert response.status_code == 400
    assert b"A product with this name already exists." in response.data
    assert product_count(app) == 1


@pytest.mark.parametrize(
    "override",
    [{"name": "ab"}, {"price": "-5"}, {"stock": "-1"}, {"image_filename": "../../evil.jpg"},
     {"vehicle_type": "boat"}, {"engine_cc": "0"}],
)
def test_invalid_input_is_refused_and_the_form_keeps_what_was_typed(app, admin, override):
    response = admin.post("/admin/products/new?type=vehicle", data={**VEHICLE_FORM, **override})

    assert response.status_code == 400
    assert product_count(app) == 0
    assert "Sport ATV" in response.get_data(as_text=True)  # the description is still in the form


def test_an_unknown_product_type_returns_404(admin):
    assert admin.get("/admin/products/new?type=boat").status_code == 404


# --- read, update, delete ---


def test_the_dashboard_lists_products_in_a_table(admin):
    admin.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    html = page(admin, "/admin/")

    assert re.search(r'<div class="table-responsive">\s*<table', html)
    assert "Yamaha Raptor 700" in html and "8,999.00 EUR" in html


def test_the_edit_form_is_prefilled(admin):
    admin.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    html = page(admin, "/admin/products/1/edit")

    assert 'value="Yamaha Raptor 700"' in html
    assert 'value="8999.00"' in html
    assert "checked" in html


def test_edit_updates_the_product_but_keeps_its_url(app, admin):
    admin.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    admin.post("/admin/products/1/edit", data={**VEHICLE_FORM, "name": "Yamaha Raptor 700R", "price": "9499.50"})

    with app.app_context():
        product = Product.query.one()
        assert product.name == "Yamaha Raptor 700R"
        assert product.price_cents == 949_950
        assert product.slug == "yamaha-raptor-700"  # old links keep working


def test_edit_with_invalid_data_changes_nothing(app, admin):
    admin.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    response = admin.post("/admin/products/1/edit", data={**VEHICLE_FORM, "price": "abc"})

    assert response.status_code == 400
    with app.app_context():
        assert Product.query.one().price_cents == 899_900


def test_delete_removes_the_product_and_its_detail_row(app, admin):
    admin.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    admin.post("/admin/products/1/delete")

    assert product_count(app) == 0
    with app.app_context():
        assert db.session.execute(text("SELECT COUNT(*) FROM vehicle_details")).scalar() == 0


def test_deleting_an_unknown_product_returns_404(admin):
    assert admin.post("/admin/products/999/delete").status_code == 404


# --- products that were ordered, and the orders list ---


def test_a_product_that_was_ordered_can_be_edited_but_not_deleted(app):
    """Regression: the edit page used to refuse ordered products, so "set its stock
    to 0 instead" (the advice shown when deleting them) could not be followed."""
    helmet_id = make_paid_order(app)
    admin = admin_client(app)

    assert admin.get(f"/admin/products/{helmet_id}/edit").status_code == 200
    admin.post(f"/admin/products/{helmet_id}/edit",
               data={"name": "Enduro Helmet Pro", "price": "189.00", "stock": "0", "gear_size": "L"})
    admin.post(f"/admin/products/{helmet_id}/delete")

    with app.app_context():
        helmet = db.session.get(Product, helmet_id)
        assert helmet is not None  # still there: the order history points at it
        assert helmet.stock == 0


def test_the_orders_list_shows_customer_total_and_status_and_is_read_only(app):
    make_paid_order(app)

    html = page(admin_client(app), "/admin/orders")

    row = re.search(r"<tr>\s*<td>#1</td>.*?</tr>", html, re.S).group(0)
    assert "ana@gmail.com" in row
    assert "378.00 EUR" in row  # 2 x 189.00, from the database
    assert '<span class="badge status-paid">paid</span>' in row
    assert "<form" not in html.split("<main")[1]  # no buttons that change an order
