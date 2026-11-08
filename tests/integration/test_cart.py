"""INTEGRATION tests: the shopping cart through the real routes and the cart page.

Rubric: N2.02 use case "shopping cart" (add, change, remove; prices always from the
database); N2.04 a table on the page; N9.01 every cart form sends a CSRF token."""

import re

import pytest

from app.extensions import db
from app.models import Product
from helpers import page, register_and_login, seed


@pytest.fixture()
def ids(app):
    return seed(app)


def add(client, product_id, quantity=1):
    return client.post(f"/cart/add/{product_id}", data={"quantity": quantity})


def cart_in_session(client):
    with client.session_transaction() as session:
        return session.get("cart", {})


def forms_for(html, product_id):
    """The two forms of a cart line: [quantity form, remove form]."""
    return re.findall(rf'<form[^>]*action="/cart/update/{product_id}".*?</form>', html, re.S)


# --- adding ---


def test_an_added_product_is_shown_in_a_table_with_the_database_price(ids, client):
    # a malicious client also sends its own price: it is ignored
    client.post(f"/cart/add/{ids['enduro-helmet-pro']}", data={"quantity": 2, "price_cents": 1})

    table = re.search(r'<div class="table-responsive">\s*<table.*?</table>', page(client, "/cart"), re.S).group(0)
    assert "Enduro Helmet Pro" in table
    assert "189.00 EUR" in table and "378.00 EUR" in table  # unit price and line total
    assert "0.01 EUR" not in table


def test_adding_the_same_product_twice_adds_up(ids, client):
    add(client, ids["enduro-helmet-pro"])
    add(client, ids["enduro-helmet-pro"])

    assert cart_in_session(client) == {str(ids["enduro-helmet-pro"]): 2}


def test_quantity_is_capped_by_the_stock(ids, client):
    add(client, ids["segway-snarler-at6-l"], 5)  # only 2 in stock

    assert cart_in_session(client) == {str(ids["segway-snarler-at6-l"]): 2}


def test_an_out_of_stock_product_cannot_be_added(app, ids, client):
    with app.app_context():
        Product.query.filter_by(slug="off-road-boots-x").one().stock = 0
        db.session.commit()

    add(client, ids["off-road-boots-x"])

    assert cart_in_session(client) == {}


def test_an_invalid_quantity_counts_as_one(ids, client):
    add(client, ids["enduro-helmet-pro"], "abc")

    assert cart_in_session(client) == {str(ids["enduro-helmet-pro"]): 1}


def test_an_unknown_product_returns_404(client):
    assert add(client, 9999).status_code == 404


# --- changing and removing ---


def test_update_sets_the_new_quantity(ids, client):
    add(client, ids["riding-gloves-trail"])

    client.post(f"/cart/update/{ids['riding-gloves-trail']}", data={"quantity": 4})

    assert cart_in_session(client) == {str(ids["riding-gloves-trail"]): 4}


@pytest.mark.parametrize("slug, expected_max", [("segway-snarler-at6-l", 2), ("enduro-helmet-pro", 10)])
def test_the_quantity_field_is_limited_and_sent_with_csrf(ids, client, slug, expected_max):
    add(client, ids[slug])
    quantity_form = forms_for(page(client, "/cart"), ids[slug])[0]

    assert 'name="csrf_token"' in quantity_form
    assert re.search(rf'name="quantity"\s+value="1"\s+min="0"\s+max="{expected_max}"', quantity_form)


def test_remove_sends_quantity_zero_and_empties_the_line(ids, client):
    add(client, ids["enduro-helmet-pro"])
    remove_form = forms_for(page(client, "/cart"), ids["enduro-helmet-pro"])[1]
    assert '<input type="hidden" name="quantity" value="0" />' in remove_form
    assert 'aria-label="Remove Enduro Helmet Pro"' in remove_form

    client.post(f"/cart/update/{ids['enduro-helmet-pro']}", data={"quantity": 0})

    assert cart_in_session(client) == {}
    assert "Your cart is empty" in page(client, "/cart")


# --- the summary panel ---


def summary(client):
    return re.search(r'<section class="panel cart-summary">.*?</section>', page(client, "/cart"), re.S).group(0)


def test_a_customer_sees_the_total_and_a_csrf_pay_form(ids, client):
    register_and_login(client)
    add(client, ids["enduro-helmet-pro"], 2)

    panel = summary(client)

    assert '<p class="cart-total">378.00 EUR</p>' in panel
    form = re.search(r'<form method="post" action="/checkout">.*?</form>', panel, re.S).group(0)
    assert 'name="csrf_token"' in form and "Pay with card" in form
    assert "Items are reserved when you continue to payment." in page(client, "/cart")


def test_a_guest_sees_log_in_to_pay_instead_of_the_pay_form(ids, client):
    add(client, ids["enduro-helmet-pro"])

    panel = summary(client)

    assert 'href="/login?next=/cart">Log in to pay</a>' in panel
    assert 'action="/checkout"' not in panel


def test_the_empty_cart_links_to_the_categories(client):
    html = page(client, "/cart")

    assert "Your cart is empty" in html
    assert 'href="/category/enduro">Shop enduro bikes</a>' in html
