import pytest

from app.extensions import db
from app.models import User
from app.services.users import create_admin

PASSWORD = "parola-sigura-123"


def add_user(app, email, role):
    with app.app_context():
        user = User(email=email, phone="0712345678", role=role)
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()


def login(client, email):
    client.post("/login", data={"email": email, "password": PASSWORD})


# Every admin URL goes through check_admin() (bp.before_request in routes/admin.py).
ADMIN_URLS = ["/admin/", "/admin/orders", "/admin/log", "/admin/products/new?type=gear"]


@pytest.mark.parametrize("url", ADMIN_URLS)
def test_anonymous_is_redirected_to_login(client, url):
    response = client.get(url)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("url", ADMIN_URLS)
def test_customer_gets_403_on_admin_pages(app, url):
    add_user(app, "ana@gmail.com", "customer")
    client = app.test_client()
    login(client, "ana@gmail.com")

    assert client.get(url).status_code == 403


def test_customer_cannot_delete_a_product(app):
    add_user(app, "ana@gmail.com", "customer")
    client = app.test_client()
    login(client, "ana@gmail.com")

    assert client.post("/admin/products/1/delete").status_code == 403


@pytest.mark.parametrize("url", ADMIN_URLS)
def test_admin_gets_access(app, url):
    add_user(app, "boss@gmail.com", "admin")
    client = app.test_client()
    login(client, "boss@gmail.com")

    assert client.get(url).status_code == 200


def test_registration_always_creates_a_customer(app, client):
    client.post(
        "/register",
        data={
            "email": "ana@gmail.com",
            "phone": "0712345678",
            "password": PASSWORD,
            "role": "admin",  # a malicious client tries to pick its own role
        },
    )

    with app.app_context():
        assert User.query.one().role == "customer"


def test_database_rejects_unknown_role(app):
    with app.app_context():
        user = User(email="x@gmail.com", phone="0712345678", role="superuser")
        user.set_password(PASSWORD)
        db.session.add(user)

        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()


def test_create_admin_service(app):
    with app.app_context():
        admin = create_admin("Admin@Shop.com", "0711111111", "parola-admin-123")

        assert admin.is_admin
        assert admin.email == "admin@shop.com"
        assert admin.check_password("parola-admin-123")


def test_create_admin_rejects_duplicates_and_bad_input(app):
    with app.app_context():
        create_admin("admin@shop.com", "0711111111", "parola-admin-123")

        with pytest.raises(ValueError):
            create_admin("admin@shop.com", "0722222222", "parola-admin-123")
        with pytest.raises(ValueError):
            create_admin("not-an-email", "0711111111", "parola-admin-123")
        with pytest.raises(ValueError):
            create_admin("other@shop.com", "123", "parola-admin-123")
        with pytest.raises(ValueError):
            create_admin("other@shop.com", "0711111111", "short")


def test_create_admin_command(app):
    result = app.test_cli_runner().invoke(
        args=["create-admin", "admin@shop.com", "0711111111"],
        input="parola-admin-123\nparola-admin-123\n",
    )

    assert result.exit_code == 0
    with app.app_context():
        assert User.query.filter_by(email="admin@shop.com").one().is_admin