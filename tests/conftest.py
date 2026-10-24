import pytest
from fake_gateway import FakeGateway

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "UPLOAD_FOLDER": str(tmp_path / "private_uploads"),
            "PAYMENT_GATEWAY": FakeGateway(),
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()