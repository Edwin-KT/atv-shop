import re

from app.cli import seed_products
from app.extensions import db
from app.models import Product


def seed(app):
    with app.app_context():
        return seed_products()


def test_catalog_lists_all_products(app, client):
    seed(app)

    html = client.get("/").get_data(as_text=True)

    assert "CFMOTO CFORCE 1000 Overland" in html
    assert "Enduro Helmet Pro" in html


def test_catalog_shows_polymorphic_summaries(app, client):
    seed(app)

    html = client.get("/").get_data(as_text=True)

    # each subclass describes itself with its own columns
    assert "ATV | 963 cc | 88 hp | street legal" in html
    assert "Riding gear | size 43" in html


def test_product_page_loads_by_slug(app, client):
    seed(app)

    response = client.get("/product/ktm-250-exc-f")

    assert response.status_code == 200
    assert b"KTM 250 EXC-F" in response.data


def test_unknown_slug_returns_404(client):
    assert client.get("/product/does-not-exist").status_code == 404


def test_seed_is_idempotent(app):
    assert seed(app) == 6
    assert seed(app) == 0


def test_images_have_alt_text(app, client):
    seed(app)

    html = client.get("/").get_data(as_text=True)

    assert 'alt="KTM 250 EXC-F"' in html
    assert 'alt="Enduro Helmet Pro"' in html


def test_product_without_a_photo_shows_the_placeholder(app, client):
    seed(app)
    with app.app_context():
        Product.query.filter_by(slug="ktm-250-exc-f").one().image_filename = None
        db.session.commit()

    assert "/static/img/placeholder.svg" in client.get("/product/ktm-250-exc-f").get_data(as_text=True)


def test_every_seeded_photo_exists_and_is_served(app, client):
    seed(app)
    html = client.get("/").get_data(as_text=True)

    photos = set(re.findall(r'src="(/static/img/products/[^"]+)"', html))
    assert len(photos) == 6
    for src in photos:
        assert client.get(src).status_code == 200, src
