"""A NUL byte in any request parameter is answered with 400 before any route
or database query runs (PostgreSQL text fields cannot store NUL)."""

from contextlib import contextmanager
from io import BytesIO

from sqlalchemy import event

from app import create_app
from app.extensions import db
from app.models import AuditLog


@contextmanager
def count_queries(app):
    """Collects every SQL statement the app sends while the block runs."""
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    with app.app_context():
        engine = db.engine
    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


def is_designed_400(response):
    html = response.get_data(as_text=True)
    return (
        response.status_code == 400
        and "Bad request" in html
        and "The request could not be processed. Please go back and try again." in html
        and 'class="page-grey"' in html
        and 'class="panel"' in html
    )


def test_nul_in_search_query_is_rejected(app, client):
    with count_queries(app) as queries:
        response = client.get("/search?q=%00")

    assert response.status_code == 400
    assert queries == []


def test_nul_in_checkout_session_id_is_rejected(app, client):
    with count_queries(app) as queries:
        response = client.get("/checkout/success?session_id=%00")

    assert response.status_code == 400  # before login_required, so no redirect
    assert queries == []


def test_nul_in_login_form_is_rejected(app, client):
    with count_queries(app) as queries:
        response = client.post(
            "/login", data={"email": "ana\x00@gmail.com", "password": "parola-sigura-123"}
        )

    assert response.status_code == 400
    assert queries == []
    with app.app_context():
        assert AuditLog.query.count() == 0  # no "login_failed" with a NUL in it


def test_nul_in_url_path_is_rejected(app, client):
    with count_queries(app) as queries:
        response = client.get("/product/abc%00")

    assert response.status_code == 400
    assert queries == []


def test_nul_in_upload_filename_is_rejected(app, client):
    with count_queries(app) as queries:
        response = client.post(
            "/documents/upload",
            data={"document": (BytesIO(b"%PDF-1.4"), "doc\x00.pdf")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    assert queries == []


def test_bad_request_page_uses_the_shop_design(client):
    assert is_designed_400(client.get("/search?q=%00"))


def test_post_without_csrf_token_gets_the_designed_page():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": True,
        }
    )

    response = app.test_client().post("/cart/add/1", data={"quantity": 1})

    assert is_designed_400(response)


def test_normal_requests_are_not_affected(client):
    assert client.get("/search?q=ktm").status_code == 200
    assert client.get("/product/no-such-product").status_code == 404
