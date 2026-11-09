"""INTEGRATION tests: browsing the shop through the real pages.

Rubric: N2.02 use case "catalog" (home page, categories, search, product page);
N2.04 content (images, text, links); N4.01 polymorphism seen on the page (each
product type describes itself). The security side of the search (XSS, SQL
injection) is in test_web_security.py."""

import re

import pytest

from app.cli import seed_products
from app.extensions import db
from app.models import Product
from app.services.catalog import MAX_QUERY_LENGTH
from helpers import page, seed


@pytest.fixture()
def seeded(app):
    seed(app)
    return app


def set_stock(app, slug, stock):
    with app.app_context():
        Product.query.filter_by(slug=slug).one().stock = stock
        db.session.commit()


# --- home and product page ---


def test_home_lists_every_product_with_its_own_summary(seeded, client):
    html = page(client, "/")

    assert "CFMOTO CFORCE 1000 Overland" in html and "Enduro Helmet Pro" in html
    assert "ATV | 963 cc | 88 hp | street legal" in html  # VehicleProduct.get_technical_summary()
    assert "Riding gear | size 43" in html  # GearProduct.get_technical_summary()


def test_product_page_shows_price_summary_and_breadcrumb(seeded, client):
    html = page(client, "/product/ktm-250-exc-f")

    assert "<h1" in html and "KTM 250 EXC-F" in html
    assert '<p class="product-detail-price">10,999.00 EUR</p>' in html  # from the database
    assert "ENDURO | 249 cc | 40 hp | off-road only" in html
    nav = re.search(r'<nav class="breadcrumb-nav".*?</nav>', html, re.S).group(0)
    assert re.findall(r'<a\s+href="([^"]+)"', nav) == ["/", "/category/enduro"]


@pytest.mark.parametrize("url", ["/product/does-not-exist", "/category/boats"])
def test_unknown_pages_return_404(client, url):
    assert client.get(url).status_code == 404


@pytest.mark.parametrize("stock, expected_max", [(2, 2), (20, 10)])
def test_quantity_on_the_product_page_is_limited_by_stock(seeded, client, stock, expected_max):
    set_stock(seeded, "enduro-helmet-pro", stock)

    form = re.search(r'<form[^>]*class="qty-form".*?</form>', page(client, "/product/enduro-helmet-pro"), re.S)

    assert re.search(rf'min="1"\s+max="{expected_max}"', form.group(0))


def test_a_sold_out_product_has_no_buy_button(seeded, client):
    set_stock(seeded, "ktm-250-exc-f", 0)

    html = page(client, "/product/ktm-250-exc-f")

    assert ">Out of stock</p>" in html
    assert "btn-buy" not in html


# --- categories and search ---


def test_category_pages_show_only_their_products(seeded, client):
    atv, gear = page(client, "/category/atv"), page(client, "/category/gear")

    assert "CFMOTO CFORCE 1000 Overland" in atv and "KTM 250 EXC-F" not in atv
    assert "Enduro Helmet Pro" in gear and "KTM 250 EXC-F" not in gear
    assert "Helmets, boots, gloves and riding gear" in gear  # the category's own title


def test_search_ignores_upper_and_lower_case(seeded, client):
    html = page(client, "/search?q=ktm")

    assert "KTM 250 EXC-F" in html and "Enduro Helmet Pro" not in html
    assert "1 result" in html


def test_search_wildcards_are_taken_literally(seeded, client):
    """A "%" typed by the user is searched for, it does not mean "anything"."""
    assert "No products match" in page(client, "/search?q=%25")


def test_an_empty_search_shows_a_hint_not_the_whole_catalog(seeded, client):
    html = page(client, "/search?q=")

    assert "Type a product name" in html
    assert "KTM 250 EXC-F" not in html


def test_a_long_search_is_cut_once_to_the_limit(seeded, client):
    html = page(client, "/search?q=" + "k" * (MAX_QUERY_LENGTH + 20))

    assert "k" * MAX_QUERY_LENGTH in html
    assert "k" * (MAX_QUERY_LENGTH + 1) not in html


def test_the_search_box_maxlength_is_the_server_limit(client):
    box = re.search(r'<input[^>]*name="q"[^>]*>', page(client, "/"), re.S).group(0)

    assert f'maxlength="{MAX_QUERY_LENGTH}"' in box


# --- images and sample data ---


def test_a_product_without_a_photo_shows_the_placeholder(seeded, client):
    with seeded.app_context():
        Product.query.filter_by(slug="ktm-250-exc-f").one().image_filename = None
        db.session.commit()

    assert "/static/img/placeholder.svg" in page(client, "/product/ktm-250-exc-f")


def test_every_sample_photo_exists_and_is_served(seeded, client):
    photos = set(re.findall(r'src="(/static/img/products/[^"]+)"', page(client, "/")))

    assert len(photos) == 6
    for src in photos:
        assert client.get(src).status_code == 200, src


def test_seeding_twice_adds_nothing_the_second_time(seeded):
    with seeded.app_context():
        assert seed_products() == 0
        assert Product.query.count() == 6
