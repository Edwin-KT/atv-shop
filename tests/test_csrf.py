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


def test_forms_contain_csrf_token():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": True,
        }
    )
    client = app.test_client()

    for url in ("/register", "/login"):
        html = client.get(url).get_data(as_text=True)
        assert 'name="csrf_token"' in html, f"{url} is missing the CSRF token"