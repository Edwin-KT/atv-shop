from app.extensions import db
from app.models import User

CREDENTIALS = {"email": "ana@gmail.com", "password": "parola-sigura-123"}


def create_user(app):
    with app.app_context():
        user = User(email=CREDENTIALS["email"], phone="0712345678")
        user.set_password(CREDENTIALS["password"])
        db.session.add(user)
        db.session.commit()


def test_login_page_loads(client):
    assert client.get("/login").status_code == 200


def test_login_with_valid_credentials(app, client):
    create_user(app)

    response = client.post("/login", data=CREDENTIALS)

    assert response.status_code == 302
    assert b"Logout" in client.get("/").data


def test_login_with_wrong_password(app, client):
    create_user(app)

    response = client.post("/login", data={**CREDENTIALS, "password": "gresita-123"})

    assert response.status_code == 401
    assert b"Logout" not in client.get("/").data


def test_login_with_unknown_email(client):
    response = client.post("/login", data=CREDENTIALS)

    assert response.status_code == 401


def test_logout(app, client):
    create_user(app)
    client.post("/login", data=CREDENTIALS)

    client.post("/logout")

    assert b"Logout" not in client.get("/").data