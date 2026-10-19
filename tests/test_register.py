from app.models import User

VALID_FORM = {
    "email": "ana@gmail.com",
    "phone": "0712345678",
    "password": "parola-sigura-123",
}


def test_register_page_loads(client):
    assert client.get("/register").status_code == 200


def test_register_creates_user_with_hashed_password(app, client):
    response = client.post("/register", data=VALID_FORM)

    assert response.status_code == 302  # redirect after success
    with app.app_context():
        user = User.query.filter_by(email="ana@gmail.com").one()
        assert user.password_hash != VALID_FORM["password"]
        assert user.check_password(VALID_FORM["password"])


def test_register_rejects_invalid_phone(app, client):
    response = client.post("/register", data={**VALID_FORM, "phone": "123"})

    assert response.status_code == 400
    with app.app_context():
        assert User.query.count() == 0


def test_register_rejects_invalid_email(client):
    response = client.post("/register", data={**VALID_FORM, "email": "not-an-email"})

    assert response.status_code == 400


def test_register_rejects_duplicate_email(client):
    client.post("/register", data=VALID_FORM)

    response = client.post("/register", data=VALID_FORM)

    assert response.status_code == 400