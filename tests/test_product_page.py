"""Product page: breadcrumb (visible + JSON-LD), spec board, buy box, trust list."""

import json
import re
from pathlib import Path

import pytest

from app.extensions import db
from app.models import GearProduct, Product, VehicleProduct
from app.seed import seed_products

ROOT = Path(__file__).resolve().parent.parent
PAGES_CSS = (ROOT / "app" / "static" / "css" / "pages.css").read_text(encoding="utf-8")
SITE = "http://127.0.0.1:5000"


@pytest.fixture()
def seeded(app):
    with app.app_context():
        seed_products()
    return app


def page(client, slug):
    return client.get(f"/product/{slug}").get_data(as_text=True)


def board(html):
    return re.search(r'<dl class="spec-board.*?</dl>', html, re.S).group(0)


def json_ld_blocks(html):
    return [
        json.loads(raw)
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    ]


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


def test_breadcrumb_json_ld_has_three_absolute_items(seeded, client):
    blocks = json_ld_blocks(page(client, "ktm-250-exc-f"))

    assert [b["@type"] for b in blocks] == ["Product", "BreadcrumbList"]
    items = blocks[1]["itemListElement"]
    assert [(i["position"], i["name"], i["item"]) for i in items] == [
        (1, "Shop", f"{SITE}/"),
        (2, "Enduro bikes", f"{SITE}/category/enduro"),
        (3, "KTM 250 EXC-F", f"{SITE}/product/ktm-250-exc-f"),
    ]
    assert all(i["@type"] == "ListItem" for i in items)


def test_breadcrumb_json_ld_escapes_the_product_name(seeded, client):
    with seeded.app_context():
        Product.query.filter_by(slug="ktm-250-exc-f").one().name = "</script><script>alert(1)"
        db.session.commit()
    html = page(client, "ktm-250-exc-f")

    assert "</script><script>alert(1)" not in html
    assert json_ld_blocks(html)[1]["itemListElement"][2]["name"] == "</script><script>alert(1)"


# --- spec board ---


def test_vehicle_spec_board_uses_the_database_values(seeded, client):
    with seeded.app_context():
        v = VehicleProduct.query.filter_by(slug="ktm-250-exc-f").one()
        cc, hp, legal = v.engine_cc, v.horsepower, v.is_street_legal
    html = board(page(client, "ktm-250-exc-f"))

    assert re.findall(r"<dt>(.*?)</dt>", html) == ["Engine", "Power", "Road use"]
    assert f'<span class="spec-number">{cc}</span> <span class="spec-unit">cc</span>' in html
    assert f'<span class="spec-number">{hp}</span> <span class="spec-unit">hp</span>' in html
    road = "Street legal" if legal else "Off-road only"
    assert f'<dd class="spec-text">{road}</dd>' in html


def test_gear_spec_board_is_one_size_cell(seeded, client):
    with seeded.app_context():
        size = GearProduct.query.filter_by(slug="enduro-helmet-pro").one().gear_size
    html = board(page(client, "enduro-helmet-pro"))

    assert 'class="spec-board spec-board-gear"' in html
    assert re.findall(r"<dt>(.*?)</dt>", html) == ["Size"]
    assert f'<dd class="spec-size">{size}</dd>' in html
    assert f"This item is sold in size {size} only." in html
    assert "cc" not in html and "hp" not in html


def test_road_use_text_may_wrap_but_is_never_cut():
    rule = re.search(r"\.spec-text\s*\{([^}]*)\}", PAGES_CSS).group(1)
    cell = re.search(r"\.spec-cell\s*\{([^}]*)\}", PAGES_CSS).group(1)

    for forbidden in ("white-space: nowrap", "text-overflow", "overflow: hidden"):
        assert forbidden not in rule
        assert forbidden not in cell
    assert "minmax(0, 1fr)" in re.search(r"\.spec-board\s*\{([^}]*)\}", PAGES_CSS).group(1)


# --- buy box ---


def test_price_has_small_decimals(seeded, client):
    html = page(client, "ktm-250-exc-f")

    assert re.search(
        r'<p class="product-detail-price"><span class="price"><span class="price-whole">10,999</span>'
        r'<span class="price-rest">\.00 EUR</span></span></p>',
        html,
    )


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
    assert photo < form < html.index('class="spec-board') < html.index('class="product-description"')


def test_sold_out_page_has_no_buy_form(seeded, client):
    with seeded.app_context():
        Product.query.filter_by(slug="ktm-250-exc-f").one().stock = 0
        db.session.commit()
    html = page(client, "ktm-250-exc-f")

    assert ">Out of stock</p>" in html
    assert "btn-buy" not in html


def test_trust_list_states_three_real_facts(seeded, client):
    trust = re.search(r'<ul class="trust-list">.*?</ul>', page(client, "ktm-250-exc-f"), re.S).group(0)

    assert re.findall(r"<span>(.*?)</span>", trust) == [
        "Secure card payment on Stripe's page",
        "Follow your order from paid to delivered",
        "Cancel an unpaid order anytime from My orders",
    ]
    assert trust.count("<svg") == 3
