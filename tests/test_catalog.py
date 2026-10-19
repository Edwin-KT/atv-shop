from app.seed import seed_products


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