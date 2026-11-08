"""Product page: breadcrumb, technical summary and buy box."""

import re

import pytest

from app.extensions import db
from app.models import Product
from app.seed import seed_products


@pytest.fixture()
def seeded(app):
    with app.app_context():
        seed_products()
    return app


def page(client, slug):
    return client.get(f"/product/{slug}").get_data(as_text=True)


# --- breadcrumb ---


@pytest.mark.parametrize(
    "slug, key, label",
    [("ktm-250-exc-f", "enduro", "Enduro bikes"),
     ("cfmoto-cforce-1000-overland", "atv", "ATVs"),
     ("enduro-helmet-pro", "gear", "Riding gear")],
)
def test_breadcrumb_links_shop_category_and_marks_the_product(seeded, client, slug, key, label):
    nav = re.search(r'<nav class="breadcrumb-nav".*?</nav>', page(client, slug), re.S).group(0)
    links = re.findall(r'<a\s+href="([^"]+)"\s*>([^<]+)</a', nav)

    assert links == [("/", "Shop"), (f"/category/{key}", label)]
    assert re.search(r'<span aria-current="page"\s*>[^<]+</span', nav)
    for href, _ in links:
        assert client.get(href).status_code == 200


# --- technical summary ---


@pytest.mark.parametrize("slug", ["ktm-250-exc-f", "enduro-helmet-pro"])
def test_technical_summary_comes_from_the_subclass(seeded, client, slug):
    with seeded.app_context():
        summary = Product.query.filter_by(slug=slug).one().get_technical_summary()

    assert f'<p class="product-specs">{summary}</p>' in page(client, slug)


# --- buy box ---


def test_price_comes_from_the_database(seeded, client):
    assert '<p class="product-detail-price">10,999.00 EUR</p>' in page(client, "ktm-250-exc-f")


@pytest.mark.parametrize("stock, expected_max", [(2, 2), (20, 10)])
def test_quantity_is_limited_by_stock_and_the_per_item_cap(seeded, client, stock, expected_max):
    with seeded.app_context():
        Product.query.filter_by(slug="enduro-helmet-pro").one().stock = stock
        db.session.commit()
    form = re.search(r'<form[^>]*class="qty-form".*?</form>', page(client, "enduro-helmet-pro"), re.S).group(0)

    assert re.search(rf'id="quantity"[^>]*min="1"\s+max="{expected_max}"', form, re.S)
    assert '<label class="visually-hidden" for="quantity">Quantity</label>' in form
    assert re.search(r'<button class="btn btn-primary btn-buy" type="submit">Add to cart</button>', form)


def test_buy_box_comes_before_specs_and_description(seeded, client):
    """On phones the page is one column, so this order keeps "Add to cart" close to the photo."""
    html = page(client, "ktm-250-exc-f")

    photo = html.index('class="product-photo')
    form = html.index('class="qty-form"')
    assert photo < form < html.index('class="product-specs"') < html.index('class="product-description"')


def test_sold_out_page_has_no_buy_form(seeded, client):
    with seeded.app_context():
        Product.query.filter_by(slug="ktm-250-exc-f").one().stock = 0
        db.session.commit()
    html = page(client, "ktm-250-exc-f")

    assert ">Out of stock</p>" in html
    assert "btn-buy" not in html
