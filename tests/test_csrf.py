from app import create_app


def test_post_without_csrf_token_is_rejected():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": True,
        }
    )
    client = app.test_client()

    response = client.post(
        "/register",
        data={"email": "ana@gmail.com", "phone": "0712345678", "password": "parola-sigura-123"},
    )

    assert response.status_code == 400