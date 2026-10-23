from app.seed import seed_products
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

    assert "963 cc" in html            # vehicle summary
    assert "size 43" in html           # gear summary


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


def test_placeholder_is_used_when_photo_file_is_missing(app, client):
    seed(app)
    with app.app_context():
        product = Product.query.filter_by(slug="ktm-250-exc-f").one()
        product.image_filename = "does-not-exist.jpg"
        db.session.commit()

    html = client.get("/product/ktm-250-exc-f").get_data(as_text=True)

    assert "placeholder.svg" in html
    assert "does-not-exist.jpg" not in html


def test_real_photo_is_used_when_file_exists(app, client, tmp_path):
    photos = tmp_path / "img" / "products"
    photos.mkdir(parents=True)
    (photos / "ktm-250-exc-f.jpg").write_bytes(b"fake-image")
    app.static_folder = str(tmp_path)  # point the app at a temporary static folder
    seed(app)

    html = client.get("/product/ktm-250-exc-f").get_data(as_text=True)

    assert "img/products/ktm-250-exc-f.jpg" in html