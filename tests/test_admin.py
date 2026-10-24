import pytest
from sqlalchemy import text

from app.extensions import db
from app.models import AuditLog, GearProduct, Product, VehicleProduct
from app.services.users import create_admin

PASSWORD = "parola-sigura-123"
ADMIN = {"email": "boss@gmail.com", "password": "parola-admin-123"}

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
GEAR_FORM = {
    "name": "Trail Jacket",
    "description": "Waterproof jacket",
    "price": "129.90",
    "stock": "10",
    "image_filename": "",
    "gear_size": "L",
}


def admin_client(app):
    with app.app_context():
        create_admin(ADMIN["email"], "0711111111", ADMIN["password"])
    client = app.test_client()
    client.post("/login", data=ADMIN)
    return client


def customer_client(app):
    client = app.test_client()
    client.post("/register", data={"email": "ana@gmail.com", "phone": "0712345678", "password": PASSWORD})
    client.post("/login", data={"email": "ana@gmail.com", "password": PASSWORD})
    return client


def product_count(app):
    with app.app_context():
        return Product.query.count()


# --- access control ---

PROTECTED = [
    ("GET", "/admin/"),
    ("GET", "/admin/products/new?type=vehicle"),
    ("POST", "/admin/products/new?type=vehicle"),
    ("GET", "/admin/products/1/edit"),
    ("POST", "/admin/products/1/delete"),
]


@pytest.mark.parametrize("method, url", PROTECTED)
def test_anonymous_is_redirected_to_login(client, method, url):
    response = client.open(url, method=method)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("method, url", PROTECTED)
def test_customer_gets_403(app, method, url):
    response = customer_client(app).open(url, method=method)

    assert response.status_code == 403


def test_customer_cannot_create_product(app):
    customer_client(app).post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    assert product_count(app) == 0


def test_navbar_shows_admin_link_only_to_admin(app):
    assert b"/admin/" in admin_client(app).get("/").data
    assert b"/admin/" not in customer_client(app).get("/").data


# --- create ---

def test_admin_creates_vehicle(app):
    client = admin_client(app)

    response = client.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    assert response.status_code == 302
    with app.app_context():
        product = Product.query.one()
        assert isinstance(product, VehicleProduct)
        assert product.slug == "yamaha-raptor-700"
        assert product.price_cents == 899_900
        assert product.is_street_legal is True


def test_admin_creates_gear(app):
    client = admin_client(app)

    client.post("/admin/products/new?type=gear", data=GEAR_FORM)

    with app.app_context():
        product = Product.query.one()
        assert isinstance(product, GearProduct)
        assert product.price_cents == 12_990
        assert product.image_filename is None


def test_same_name_gets_a_unique_slug(app):
    client = admin_client(app)

    client.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)
    client.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    with app.app_context():
        assert {p.slug for p in Product.query.all()} == {
            "yamaha-raptor-700",
            "yamaha-raptor-700-2",
        }


@pytest.mark.parametrize(
    "override",
    [
        {"name": "ab"},
        {"price": "abc"},
        {"price": "-5"},
        {"stock": "-1"},
        {"image_filename": "../../evil.jpg"},
        {"image_filename": "photo.exe"},
        {"vehicle_type": "boat"},
        {"engine_cc": "0"},
        {"horsepower": "abc"},
    ],
)
def test_invalid_input_is_rejected(app, override):
    client = admin_client(app)

    response = client.post("/admin/products/new?type=vehicle", data={**VEHICLE_FORM, **override})

    assert response.status_code == 400
    assert product_count(app) == 0


def test_invalid_form_keeps_what_the_admin_typed(app):
    client = admin_client(app)

    html = client.post(
        "/admin/products/new?type=vehicle", data={**VEHICLE_FORM, "price": "abc"}
    ).get_data(as_text=True)

    assert "Yamaha Raptor 700" in html
    assert "Price must be" in html


def test_unknown_product_type_returns_404(app):
    assert admin_client(app).get("/admin/products/new?type=boat").status_code == 404


def test_product_name_is_escaped_in_html(app):
    client = admin_client(app)
    client.post(
        "/admin/products/new?type=gear",
        data={**GEAR_FORM, "name": "<script>alert(1)</script>"},
    )

    html = client.get("/admin/").get_data(as_text=True)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# --- list, edit, delete ---

def test_dashboard_lists_products(app):
    client = admin_client(app)
    client.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    html = client.get("/admin/").get_data(as_text=True)

    assert "Yamaha Raptor 700" in html


def test_edit_form_is_prefilled(app):
    client = admin_client(app)
    client.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    html = client.get("/admin/products/1/edit").get_data(as_text=True)

    assert 'value="Yamaha Raptor 700"' in html
    assert 'value="8999.00"' in html
    assert "checked" in html


def test_edit_updates_product_but_keeps_slug(app):
    client = admin_client(app)
    client.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    response = client.post(
        "/admin/products/1/edit",
        data={**VEHICLE_FORM, "name": "Yamaha Raptor 700R", "price": "9499.50"},
    )

    assert response.status_code == 302
    with app.app_context():
        product = Product.query.one()
        assert product.name == "Yamaha Raptor 700R"
        assert product.price_cents == 949_950
        assert product.slug == "yamaha-raptor-700"  # URL stays stable


def test_edit_with_invalid_data_changes_nothing(app):
    client = admin_client(app)
    client.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    response = client.post("/admin/products/1/edit", data={**VEHICLE_FORM, "price": "abc"})

    assert response.status_code == 400
    with app.app_context():
        assert Product.query.one().price_cents == 899_900


def test_delete_removes_product_and_its_detail_row(app):
    client = admin_client(app)
    client.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    response = client.post("/admin/products/1/delete")

    assert response.status_code == 302
    with app.app_context():
        assert Product.query.count() == 0
        assert db.session.execute(text("SELECT COUNT(*) FROM vehicle_details")).scalar() == 0


def test_delete_unknown_product_returns_404(app):
    assert admin_client(app).post("/admin/products/999/delete").status_code == 404


def test_admin_actions_are_audited(app):
    client = admin_client(app)
    client.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)
    client.post("/admin/products/1/edit", data=VEHICLE_FORM)
    client.post("/admin/products/1/delete")

    with app.app_context():
        events = [e.event_type for e in AuditLog.query.order_by(AuditLog.id)]

    assert events[-3:] == ["product_created", "product_updated", "product_deleted"]

def test_admin_can_read_audit_log(app):
    client = admin_client(app)
    client.post("/admin/products/new?type=vehicle", data=VEHICLE_FORM)

    html = client.get("/admin/logs").get_data(as_text=True)

    assert "product_created" in html
    assert "login_success" in html