"""Cart page: stepper without JavaScript, remove button and summary."""

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


def page(client, url):
    return client.get(url).get_data(as_text=True)


def stepper(html, product_id):
    return re.search(
        rf'<form\s+class="qty-stepper"\s+method="post"\s+action="/cart/update/{product_id}".*?</form>',
        html,
        re.S,
    ).group(0)


def buttons(form):
    """(value, aria-label, disabled) for each stepper button."""
    found = []
    for button in re.findall(r"<button.*?</button>", form, re.S):
        value = re.search(r'value="(-?\d+)"', button).group(1)
        label = re.search(r'aria-label="([^"]+)"', button).group(1)
        found.append((int(value), label, "disabled" in button))
    return found


# --- stepper ---


def test_stepper_buttons_send_one_less_and_one_more(ids, client):
    add(client, ids["enduro-helmet-pro"], 2)
    form = stepper(page(client, "/cart"), ids["enduro-helmet-pro"])

    assert buttons(form) == [
        (1, "Decrease quantity of Enduro Helmet Pro", False),
        (3, "Increase quantity of Enduro Helmet Pro", False),
    ]
    assert 'name="csrf_token"' in form
    assert not re.search(r'<input[^>]*name="quantity"', form)  # the buttons carry the value
    assert re.search(r'<span class="visually-hidden">Quantity: </span>2</span', form)


def test_minus_is_disabled_at_one(ids, client):
    add(client, ids["enduro-helmet-pro"], 1)
    (_, _, minus_disabled), (_, _, plus_disabled) = buttons(
        stepper(page(client, "/cart"), ids["enduro-helmet-pro"])
    )

    assert minus_disabled and not plus_disabled


@pytest.mark.parametrize(
    "slug, quantity", [("segway-snarler-at6-l", 2), ("enduro-helmet-pro", 10)]
)
def test_plus_is_disabled_at_the_stock_or_the_per_item_cap(ids, client, slug, quantity):
    add(client, ids[slug], quantity)  # segway: stock 2; helmet: stock 20, cap 10
    (_, _, plus_disabled) = buttons(stepper(page(client, "/cart"), ids[slug]))[1]

    assert plus_disabled


def test_a_forced_plus_past_the_limit_stays_at_the_limit(app, ids, client):
    add(client, ids["segway-snarler-at6-l"], 2)

    client.post(f"/cart/update/{ids['segway-snarler-at6-l']}", data={"quantity": 3})

    form = stepper(page(client, "/cart"), ids["segway-snarler-at6-l"])
    assert re.search(r"Quantity: </span>2</span", form)


def test_remove_button_is_labelled_and_protected(ids, client):
    add(client, ids["enduro-helmet-pro"], 1)
    html = page(client, "/cart")
    form = re.search(
        rf'<form\s+method="post"\s+action="/cart/remove/{ids["enduro-helmet-pro"]}".*?</form>', html, re.S
    ).group(0)

    assert 'name="csrf_token"' in form
    assert 'aria-label="Remove Enduro Helmet Pro"' in form
    assert re.search(r">\s*Remove\s*</button>", form)


# --- summary ---


def test_summary_has_the_total_and_the_checkout_button(ids, client):
    add(client, ids["enduro-helmet-pro"], 2)
    summary = re.search(r'<section class="panel cart-summary">.*?</section>', page(client, "/cart"), re.S).group(0)

    assert "378.00 EUR" in summary
    assert re.search(r'href="/checkout"\s*>Proceed to checkout</a', summary)


def test_cart_explains_when_items_are_reserved(ids, client):
    add(client, ids["enduro-helmet-pro"], 1)
    html = page(client, "/cart")

    assert "Items are reserved when you continue to payment." in html
    assert "not reserved" not in html


def test_empty_cart_has_no_steps_and_links_to_categories(client):
    html = page(client, "/cart")

    assert "Your cart is empty" in html
    assert re.search(r'href="/category/enduro"\s*>Shop enduro bikes</a', html)
    assert re.search(r'href="/category/atv"\s*>Shop ATVs</a', html)
