from app import create_app

TEST_CONFIG = {
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
}


def test_health_endpoint_returns_ok():
    client = create_app(TEST_CONFIG).test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_database_health_endpoint_returns_ok():
    client = create_app(TEST_CONFIG).test_client()

    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.get_json() == {"database": "ok"}