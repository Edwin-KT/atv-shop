"""Design language: shop pages are white, other pages grey with white panels,
product cards have a quick-add "+" button, and the 404 page uses the shop design."""

import re

from app.extensions import db
from app.models import Product
from app.seed import seed_products
from app.services.users import create_admin

ADMIN = {"email": "boss@gmail.com", "password": "parola-admin-123"}


def seed(app, stocks=None):
    """Seed the sample products, then optionally override stock by slug."""
    with app.app_context():
        seed_products()
        for product in Product.query.all():
            product.stock = (stocks or {}).get(product.slug, 10)
        db.session.commit()
        return {p.slug: p.id for p in Product.query.all()}


def admin_client(app):
    with app.app_context():
        create_admin(ADMIN["email"], "0711111111", ADMIN["password"])
    client = app.test_client()
    client.post("/login", data=ADMIN)
    return client


def body_is_grey(html):
    body = re.search(r"<body([^>]*)>", html).group(1)
    return "page-grey" in body


def panel_count(html):
    """Elements whose class list contains the token `panel` (not `panel-title`)."""
    return sum(
        1 for classes in re.findall(r'class="([^"]*)"', html) if "panel" in classes.split()
    )


def card_for(html, slug):
    """The <article> of one product card."""
    for card in re.findall(r'<article class="product-card">.*?</article>', html, re.S):
        if f"/product/{slug}" in card:
            return card
    raise AssertionError(f"no card for {slug}")


# --- quick-add ---


def test_quick_add_is_a_csrf_post_form_with_quantity_one(app, client):
    ids = seed(app)
    card = card_for(client.get("/").get_data(as_text=True), "ktm-250-exc-f")

    form = re.search(r'<form\s+class="quick-add"(.*?)</form>', card, re.S).group(0)
    assert 'method="post"' in form
    assert f'action="/cart/add/{ids["ktm-250-exc-f"]}"' in form
    assert 'name="csrf_token"' in form
    assert re.search(r'name="quantity"\s+value="1"', form)
    assert 'class="quick-add-btn"' in form


def test_quick_add_adds_one_item_to_the_cart(app, client):
    ids = seed(app)

    response = client.post(f"/cart/add/{ids['ktm-250-exc-f']}", data={"quantity": "1"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/cart")

    html = client.get("/cart").get_data(as_text=True)
    assert "Your cart (1)" in html


def test_sold_out_product_has_no_quick_add_and_a_sold_out_tag(app, client):
    seed(app, {"ktm-250-exc-f": 0})
    card = card_for(client.get("/").get_data(as_text=True), "ktm-250-exc-f")

    assert "Sold out" in card
    assert "tag-out" in card
    assert "quick-add" not in card


def test_low_stock_product_has_a_low_stock_tag(app, client):
    seed(app, {"ktm-250-exc-f": 2})
    html = client.get("/").get_data(as_text=True)
    card = card_for(html, "ktm-250-exc-f")

    assert "Low stock" in card
    assert "tag-hot" in card
    assert "quick-add-btn" in card  # still buyable
    other = card_for(html, "enduro-helmet-pro")  # stock 10: no tag
    assert 'class="tag' not in other


# --- page backgrounds and panels ---


def test_shop_pages_are_white_without_a_panel(app, client):
    seed(app)
    for url in ["/", "/category/atv", "/search?q=ktm", "/product/ktm-250-exc-f"]:
        html = client.get(url).get_data(as_text=True)
        assert not body_is_grey(html), url
        assert panel_count(html) == 0, url


def test_account_pages_are_grey_with_one_panel(app, client):
    for url in ["/login", "/register"]:
        html = client.get(url).get_data(as_text=True)
        assert body_is_grey(html), url
        assert panel_count(html) == 1, url

    admin = admin_client(app)
    for url in ["/documents", "/orders", "/admin/", "/admin/logs"]:
        response = admin.get(url)
        assert response.status_code == 200, url
        html = response.get_data(as_text=True)
        assert body_is_grey(html), url
        assert panel_count(html) == 1, url


def test_cart_is_grey_without_a_double_panel(app, client):
    ids = seed(app)

    empty = client.get("/cart").get_data(as_text=True)
    assert body_is_grey(empty)
    assert panel_count(empty) == 1

    client.post(f"/cart/add/{ids['ktm-250-exc-f']}", data={"quantity": "1"})
    full = client.get("/cart").get_data(as_text=True)
    assert body_is_grey(full)
    assert panel_count(full) == 2  # items panel + "Total amount" panel
    assert re.search(r'class="[^"]*\bpanel\b[^"]*\bcart-summary\b', full)
    # The content wrapper in base.html is not a panel, so panels are not nested.
    main = re.search(r'<main class="container">\s*(?:<div class="alert[^>]*>.*?</div>\s*)*<div>', full, re.S)
    assert main, "the content wrapper must not have the panel class"


# --- product page ---


def test_product_page_uses_the_new_layout(app, client):
    ids = seed(app)
    html = client.get("/product/ktm-250-exc-f").get_data(as_text=True)

    assert re.search(r'class="product-photo ratio ratio-1x1"', html)
    assert 'class="product-detail-price"' in html
    assert 'class="stock-label"' in html
    assert '<nav class="breadcrumb-nav" aria-label="Breadcrumb">' in html
    form = re.search(r'<form[^>]*qty-form.*?</form>', html, re.S).group(0)
    assert f'action="/cart/add/{ids["ktm-250-exc-f"]}"' in form
    assert 'name="csrf_token"' in form
    assert 'name="quantity"' in form


def test_sold_out_product_page_has_no_add_form(app, client):
    seed(app, {"ktm-250-exc-f": 0})
    html = client.get("/product/ktm-250-exc-f").get_data(as_text=True)

    assert "stock-label-out" in html
    assert "qty-form" not in html


# --- 404 ---


def test_404_uses_the_shop_design(client):
    response = client.get("/this-page-does-not-exist")
    html = response.get_data(as_text=True)

    assert response.status_code == 404
    assert "Page not found" in html
    assert "Back to the shop" in html
    assert body_is_grey(html)
    assert panel_count(html) == 1


def test_missing_product_returns_the_designed_404(client):
    response = client.get("/product/no-such-product")

    assert response.status_code == 404
    assert "Page not found" in response.get_data(as_text=True)
