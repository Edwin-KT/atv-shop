"""UNIT tests for app/services/cart.py: the cart functions called directly, inside a
fake request (the cart lives in the session cookie; no HTTP client).

Rubric: N2.02 use case "shopping cart" (quantities limited by stock, prices always
from the database); N3.01 the CartLine class; N6.01 unit tests."""

import pytest

from app.extensions import db
from app.models import Product
from app.services.cart import (
    MAX_QUANTITY_PER_ITEM,
    CartLine,
    add_item,
    cart_item_count,
    cart_total_cents,
    get_cart_lines,
    set_quantity,
)
from helpers import seed


def get(slug):
    return Product.query.filter_by(slug=slug).one()


@pytest.mark.parametrize(
    "slug, expected",
    [("segway-snarler-at6-l", 2), ("enduro-helmet-pro", MAX_QUANTITY_PER_ITEM)],
    ids=["limited by stock (2)", "limited by the per-item cap (10)"],
)
def test_max_quantity_is_the_stock_but_at_most_10(app, slug, expected):
    seed(app)
    with app.app_context():
        assert CartLine(get(slug), 1).max_quantity == expected


def test_adding_accumulates_but_never_passes_the_stock(app):
    seed(app)
    with app.test_request_context():
        helmet, segway = get("enduro-helmet-pro"), get("segway-snarler-at6-l")

        add_item(helmet)
        add_item(helmet, 2)
        assert add_item(segway, 5) == 2  # only 2 in stock

        assert cart_item_count() == 5  # 3 helmets + 2 ATVs


def test_an_out_of_stock_product_is_not_added(app):
    seed(app)
    with app.test_request_context():
        boots = get("off-road-boots-x")
        boots.stock = 0
        db.session.commit()

        assert add_item(boots) == 0
        assert cart_item_count() == 0


def test_quantity_zero_removes_the_line(app):
    seed(app)
    with app.test_request_context():
        helmet = get("enduro-helmet-pro")
        add_item(helmet, 2)

        set_quantity(helmet, 0)

        assert get_cart_lines() == []


def test_the_total_uses_the_prices_from_the_database(app):
    seed(app)
    with app.test_request_context():
        add_item(get("riding-gloves-trail"), 2)  # 2 x 49.00
        add_item(get("enduro-helmet-pro"), 1)  # 1 x 189.00

        assert cart_total_cents(get_cart_lines()) == 28_700
