import pytest

from app.extensions import db
from app.models import User
from app.security import admin_required
from app.services.users import create_admin

PASSWORD = "parola-sigura-123"


@pytest.fixture()
def protected_app(app):
    """The app plus a throwaway admin-only route, used just to test the decorator."""

    @app.get("/admin-only")
    @admin_required
    def admin_only():
        return "secret"

    return app


def add_user(app, email, role):
    with app.app_context():
        user = User(email=email, phone="0712345678", role=role)
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()


def login(client, email):
    client.post("/login", data={"email": email, "password": PASSWORD})


def test_anonymous_is_redirected_to_login(protected_app):
    response = protected_app.test_client().get("/admin-only")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_customer_gets_403(protected_app):
    add_user(protected_app, "ana@gmail.com", "customer")
    client = protected_app.test_client()
    login(client, "ana@gmail.com")

    assert client.get("/admin-only").status_code == 403


def test_admin_gets_access(protected_app):
    add_user(protected_app, "boss@gmail.com", "admin")
    client = protected_app.test_client()
    login(client, "boss@gmail.com")

    response = client.get("/admin-only")

    assert response.status_code == 200
    assert response.data == b"secret"


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