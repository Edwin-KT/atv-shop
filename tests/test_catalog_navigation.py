import pytest

from app.seed import seed_products


@pytest.fixture()
def seeded(app):
    with app.app_context():
        seed_products()
    return app


def test_category_pages_show_only_their_products(seeded, client):
    atv = client.get("/category/atv").get_data(as_text=True)
    enduro = client.get("/category/enduro").get_data(as_text=True)
    gear = client.get("/category/gear").get_data(as_text=True)

    assert "CFMOTO CFORCE 1000 Overland" in atv and "KTM 250 EXC-F" not in atv
    assert "KTM 250 EXC-F" in enduro and "CFMOTO" not in enduro
    assert "Enduro Helmet Pro" in gear and "KTM 250 EXC-F" not in gear


def test_unknown_category_returns_404(client):
    assert client.get("/category/boats").status_code == 404


def test_category_pages_have_their_own_title_and_description(seeded, client):
    html = client.get("/category/gear").get_data(as_text=True)

    assert "Helmets, boots, gloves and riding gear" in html
    assert "Protective riding gear" in html


def test_search_finds_products_case_insensitively(seeded, client):
    html = client.get("/search?q=ktm").get_data(as_text=True)

    assert "KTM 250 EXC-F" in html
    assert "Enduro Helmet Pro" not in html
    assert "1 result" in html


def test_search_wildcards_are_taken_literally(seeded, client):
    html = client.get("/search?q=%25").get_data(as_text=True)  # a single "%"

    assert "No products match" in html


def test_empty_search_shows_a_hint_not_the_whole_catalog(seeded, client):
    html = client.get("/search?q=").get_data(as_text=True)

    assert "Type a product name" in html
    assert "KTM 250 EXC-F" not in html


def test_search_text_is_escaped(client):
    html = client.get("/search?q=<script>alert(1)</script>").get_data(as_text=True)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_search_pages_are_not_indexed(client):
    assert "noindex" in client.get("/search?q=ktm").headers["X-Robots-Tag"]


def test_home_page_links_to_every_category_with_products(seeded, client):
    html = client.get("/").get_data(as_text=True)

    for key in ("atv", "enduro", "gear"):
        assert f"/category/{key}" in html


def test_home_page_has_no_category_tiles_without_products(client):
    assert "Shop by category" not in client.get("/").get_data(as_text=True)


def test_navigation_links_to_every_category(client):
    html = client.get("/").get_data(as_text=True)

    for key in ("atv", "enduro", "gear"):
        assert f"/category/{key}" in html
    assert 'role="search"' in html


def test_active_category_is_highlighted(client):
    html = client.get("/category/gear").get_data(as_text=True)

    assert html.count("is-active") == 1


def test_hero_is_outside_the_main_container(seeded, client):
    html = client.get("/").get_data(as_text=True)

    assert html.index('id="heroCarousel"') < html.index("<main")