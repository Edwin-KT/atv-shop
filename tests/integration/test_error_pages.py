"""INTEGRATION tests: an unexpected error shows our own 500 page, never a crash or details.

Rubric: N4.02 exception handling (one error handler for every expected status, 500 included)."""

import pytest

from app.extensions import db
from app.models import Product
from helpers import register_and_login, seed


@pytest.fixture()
def failing_app(app):
    """The test app with two routes that fail. In tests Flask normally re-raises
    exceptions; PROPAGATE_EXCEPTIONS=False makes it behave like production."""
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret detail from the code")

    @app.get("/boom-db")
    def boom_db():
        taken_slug = Product.query.first().slug
        db.session.add(Product(name="Copy", slug=taken_slug, description="x", price_cents=1, stock=1))
        db.session.commit()  # fails: the slug must be unique

    return app


def test_an_unexpected_error_shows_our_500_page(failing_app):
    response = failing_app.test_client().get("/boom")
    html = response.get_data(as_text=True)

    assert response.status_code == 500
    assert "Something went wrong" in html
    assert '<section class="panel">' in html and "navbar" in html  # the site's design
    assert "secret detail" not in html and "RuntimeError" not in html
    assert "Content-Security-Policy" in response.headers


def test_the_500_page_still_works_after_a_failed_database_commit(failing_app):
    seed(failing_app)
    client = register_and_login(failing_app.test_client())  # the navbar loads the user from the DB

    response = client.get("/boom-db")

    assert response.status_code == 500
    assert "Something went wrong" in response.get_data(as_text=True)


def test_the_500_is_logged(failing_app, log_text):
    failing_app.test_client().get("/boom")

    assert "GET '/boom' status=500" in log_text()
