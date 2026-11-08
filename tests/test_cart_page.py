"""Cart page: a table of lines with a quantity form (no JavaScript), remove button and total."""

import re

import pytest

from app.models import Product
from app.seed import seed_products


@pytest.fixture()
def ids(app):
    with app.app_context():
        seed_products()
        return {p.slug: p.id for p in Product.query.all()}


def add(client, product_id, quantity):
    client.post(f"/cart/add/{product_id}", data={"quantity": quantity})


def page(client, url="/cart"):
    return client.get(url).get_data(as_text=True)


def forms_for(html, product_id):
    """Every form that posts to /cart/update/<id> (the quantity form and the remove form)."""
    return re.findall(
        rf'<form[^>]*action="/cart/update/{product_id}".*?</form>', html, re.S
    )


def test_cart_lines_are_a_responsive_table(ids, client):
    add(client, ids["enduro-helmet-pro"], 2)
    html = page(client)

    table = re.search(r'<div class="table-responsive">\s*<table.*?</table>', html, re.S).group(0)
    assert "Enduro Helmet Pro" in table
    assert "189.00 EUR" in table  # unit price
    assert "378.00 EUR" in table  # line total


@pytest.mark.parametrize("slug, expected_max", [("segway-snarler-at6-l", 2), ("enduro-helmet-pro", 10)])
def test_quantity_input_is_limited_by_stock_and_the_per_item_cap(ids, client, slug, expected_max):
    add(client, ids[slug], 1)  # segway: stock 2; helmet: stock 20, capped at 10
    quantity_form = forms_for(page(client), ids[slug])[0]

    assert 'name="csrf_token"' in quantity_form
    assert re.search(rf'name="quantity"\s+value="1"\s+min="0"\s+max="{expected_max}"', quantity_form)


def test_a_quantity_past_the_limit_stays_at_the_limit(ids, client):
    add(client, ids["segway-snarler-at6-l"], 2)

    client.post(f"/cart/update/{ids['segway-snarler-at6-l']}", data={"quantity": 3})

    quantity_form = forms_for(page(client), ids["segway-snarler-at6-l"])[0]
    assert re.search(r'name="quantity"\s+value="2"', quantity_form)


def test_remove_button_sends_quantity_zero_with_csrf(ids, client):
    add(client, ids["enduro-helmet-pro"], 1)
    remove_form = forms_for(page(client), ids["enduro-helmet-pro"])[1]

    assert 'name="csrf_token"' in remove_form
    assert '<input type="hidden" name="quantity" value="0" />' in remove_form
    assert 'aria-label="Remove Enduro Helmet Pro"' in remove_form

    client.post(f"/cart/update/{ids['enduro-helmet-pro']}", data={"quantity": 0})
    assert "Your cart is empty" in page(client)


def summary_of(client):
    return re.search(r'<section class="panel cart-summary">.*?</section>', page(client), re.S).group(0)


def test_summary_panel_has_the_total_and_the_pay_form(ids, client):
    client.post("/register", data={"email": "ana@gmail.com", "phone": "0712345678", "password": "parola-sigura-123"})
    client.post("/login", data={"email": "ana@gmail.com", "password": "parola-sigura-123"})
    add(client, ids["enduro-helmet-pro"], 2)
    summary = summary_of(client)

    assert '<p class="cart-total">378.00 EUR</p>' in summary
    assert re.search(r'<form method="post" action="/checkout">.*Pay with card</button>', summary, re.S)
    assert "Log in to pay" not in summary


def test_anonymous_cart_shows_a_login_link_instead_of_the_pay_form(ids, client):
    add(client, ids["enduro-helmet-pro"], 1)
    summary = summary_of(client)

    assert 'href="/login?next=/cart">Log in to pay</a>' in summary
    assert 'action="/checkout"' not in summary


def test_cart_explains_when_items_are_reserved(ids, client):
    add(client, ids["enduro-helmet-pro"], 1)

    assert "Items are reserved when you continue to payment." in page(client)


def test_empty_cart_links_to_categories(client):
    html = page(client)

    assert "Your cart is empty" in html
    assert 'href="/category/enduro">Shop enduro bikes</a>' in html
    assert 'href="/category/atv">Shop ATVs</a>' in html
