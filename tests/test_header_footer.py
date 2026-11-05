"""Header (utility bar, wordmark, tabs, search, icons, burger menu) and footer."""

import re

import pytest

from app.seed import seed_products
from app.services.users import create_admin

PASSWORD = "parola-sigura-123"


def customer(client, email="ana@gmail.com"):
    client.post("/register", data={"email": email, "phone": "0712345678", "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client


def admin(app):
    with app.app_context():
        create_admin("boss@gmail.com", "0711111111", "parola-admin-123")
    client = app.test_client()
    client.post("/login", data={"email": "boss@gmail.com", "password": "parola-admin-123"})
    return client


def header_of(html):
    return re.search(r'<header class="site-header">.*?</header>', html, re.S).group(0)


def footer_of(html):
    return re.search(r'<footer class="site-footer">.*?</footer>', html, re.S).group(0)


def page(client, url="/"):
    return client.get(url).get_data(as_text=True)


# --- account links depend on who is logged in ---


def test_anonymous_header_offers_login_and_register(client):
    header = header_of(page(client))

    assert 'href="/login"' in header
    assert 'href="/register"' in header
    assert "Logout" not in header
    assert 'href="/documents"' not in header
    assert 'href="/admin/"' not in header
    assert re.search(r'class="header-icon" href="/login" aria-label="Login"', header)


def test_customer_header_links_and_logout_forms(client):
    header = header_of(page(customer(client)))

    assert re.search(r'<a href="/orders">Order status</a>', header)
    assert 'href="/documents"' in header
    assert 'href="/admin/"' not in header
    assert re.search(r'class="header-icon" href="/orders" aria-label="My orders"', header)
    # One logout form in the desktop utility bar, one in the phone menu; both POST with CSRF.
    forms = re.findall(r'<form method="post" action="/logout">.*?</form>', header, re.S)
    assert len(forms) == 2
    assert all('name="csrf_token"' in form for form in forms)


def test_admin_sees_the_admin_link(app):
    header = header_of(page(admin(app)))

    assert re.search(r'class="account-admin" href="/admin/"', header)


# --- wordmark, search, tabs ---


def test_wordmark_links_home_with_a_label(client):
    header = header_of(page(client))

    assert re.search(r'class="wordmark"\s+href="/"\s+aria-label="ATV &amp; Enduro Shop, home"', header)


def test_search_form_is_labelled(client):
    header = header_of(page(client))
    form = re.search(r'<form\s+class="header-search".*?</form>', header, re.S).group(0)

    assert 'role="search"' in form
    assert 'action="/search"' in form
    assert 'method="get"' in form
    assert '<label class="visually-hidden" for="site-search">Search products</label>' in form
    assert re.search(r'id="site-search"[^>]*name="q"', form, re.S)
    assert 'aria-label="Search"' in form


@pytest.mark.parametrize(
    "url, active",
    [("/", "All"), ("/category/atv", "ATVs"), ("/category/enduro", "Enduro bikes"),
     ("/category/gear", "Riding gear")],
)
def test_exactly_one_tab_is_active_and_marked_as_current(client, url, active):
    tabs = re.search(r'<nav class="segment-tabs".*?</nav>', page(client, url), re.S).group(0)

    assert tabs.count("is-active") == 1
    assert tabs.count('aria-current="page"') == 1
    assert re.search(rf'class="is-active"\s+aria-current="page"\s*>{active}</a', tabs)


def test_no_tab_is_active_on_a_product_page(app, client):
    with app.app_context():
        seed_products()
    tabs = re.search(r'<nav class="segment-tabs".*?</nav>', page(client, "/product/ktm-250-exc-f"), re.S).group(0)

    assert "is-active" not in tabs


# --- icons and cart count ---


def test_cart_count_is_hidden_when_the_cart_is_empty(client):
    header = header_of(page(client))

    assert "cart-count" not in header
    assert 'aria-label="Cart, 0 items"' in header


def test_cart_count_is_a_light_badge_once_something_is_in_the_cart(app, client):
    with app.app_context():
        seed_products()
    client.post("/cart/add/1", data={"quantity": 1})
    header = header_of(page(client))

    assert '<span class="badge cart-count text-bg-light">1</span>' in header
    assert 'aria-label="Cart, 1 item"' in header


def test_burger_opens_the_account_menu(client):
    header = header_of(page(client))
    button = re.search(r"<button\s+class=\"navbar-toggler[^>]*>", header, re.S).group(0)

    assert 'data-bs-target="#siteMenu"' in button
    assert 'aria-controls="siteMenu"' in button
    assert 'aria-expanded="false"' in button
    assert 'aria-label="Open account menu"' in button
    assert re.search(r'class="collapse header-menu d-lg-none" id="siteMenu"', header)


# --- footer ---


def test_footer_has_real_columns_and_the_livery_edge(client):
    footer = footer_of(page(client))

    assert re.findall(r"<h2>(.*?)</h2>", footer) == ["Shop", "Account", "Paying &amp; delivery"]
    assert '<span class="livery" aria-hidden="true"></span>' in footer


@pytest.mark.parametrize("logged_in", [False, True])
def test_every_footer_link_works(app, client, logged_in):
    with app.app_context():
        seed_products()
    if logged_in:
        customer(client)
    hrefs = re.findall(r'href="([^"]+)"', footer_of(page(client)))

    assert hrefs
    for href in hrefs:
        assert client.get(href).status_code in (200, 302), href


@pytest.mark.parametrize("url", ["/", "/category/enduro", "/cart", "/login"])
def test_no_reference_shop_branding(client, url):
    assert "24mx" not in page(client, url).lower()
