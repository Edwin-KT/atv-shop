"""UNIT tests for app/services/catalog.py: the category and search queries, called
directly (no HTTP).

Rubric: N2.02 use case "catalog" (categories and search); N6.01 unit tests.
The security side of the search (XSS, SQL injection) is in
tests/integration/test_web_security.py."""

import pytest

from app.services.catalog import (
    CATEGORIES,
    MAX_QUERY_LENGTH,
    clean_query,
    products_in_category,
    search_products,
)
from helpers import seed


def names(products):
    return [product.name for product in products]


@pytest.mark.parametrize("key", list(CATEGORIES))
def test_each_category_has_only_its_own_products_sorted_by_name(app, key):
    seed(app)
    with app.app_context():
        products = products_in_category(key)

        assert products, key
        assert all(product.category_key == key for product in products)
        assert names(products) == sorted(names(products))


def test_the_search_text_loses_outer_spaces_and_is_cut_to_the_limit():
    assert clean_query("  ktm  ") == "ktm"
    assert clean_query("x" * 100) == "x" * MAX_QUERY_LENGTH


def test_search_ignores_upper_and_lower_case(app):
    seed(app)
    with app.app_context():
        assert names(search_products("ktm")) == ["KTM 250 EXC-F"]
        assert names(search_products("KTM")) == ["KTM 250 EXC-F"]


@pytest.mark.parametrize("text", ["%", "_", ""])
def test_wildcards_are_literal_and_an_empty_text_finds_nothing(app, text):
    seed(app)
    with app.app_context():
        assert search_products(text) == []
