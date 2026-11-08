"""UNIT tests for app/validators.py: plain functions, called directly (no app, no HTTP).

Rubric: N3.03 the account data is checked on the server (email, phone with exactly
10 digits, password); N2.02 the admin's product form (price, numbers, image name);
N6.01 unit tests."""

import pytest
from werkzeug.datastructures import MultiDict

from app.validators import (
    is_valid_email,
    is_valid_password,
    is_valid_phone,
    parse_int,
    parse_price_to_cents,
    slugify,
    validate_product_form,
)

GEAR_FORM = {"name": "Trail Jacket", "price": "129.90", "stock": "10", "gear_size": "L"}


# --- accounts ---


@pytest.mark.parametrize("value", ["ana@gmail.com", "ion.popescu+shop@yahoo.com"])
def test_valid_emails(value):
    assert is_valid_email(value)


@pytest.mark.parametrize("value", ["", "ana", "ana@", "an a@gmail.com"])
def test_invalid_emails(value):
    assert not is_valid_email(value)


def test_a_phone_with_exactly_10_digits_is_valid():
    assert is_valid_phone("0712345678")


@pytest.mark.parametrize(
    "value", ["", "071234567", "07123456789", "07123abc78", "0712 345 678", "0712345678\n"]
)
def test_any_other_phone_is_invalid(value):
    """9 digits, 11 digits, letters, spaces and a hidden newline are all refused."""
    assert not is_valid_phone(value)


def test_password_needs_at_least_8_characters():
    assert is_valid_password("12345678")
    assert not is_valid_password("1234567")


# --- the admin's product form ---


def test_slugify_makes_a_clean_url_part():
    assert slugify("KTM 250 EXC-F") == "ktm-250-exc-f"
    assert slugify("Cască Enduro  Pro!") == "casca-enduro-pro"
    assert slugify("!!!") == ""


@pytest.mark.parametrize(
    "value, cents",
    [("189", 18900), ("189,5", 18950), ("0.99", 99), (" 5.05 ", 505),
     ("0.29", 29), ("1.15", 115)],  # with float, the last two would give 28 and 114
)
def test_valid_prices_become_exact_cents(value, cents):
    assert parse_price_to_cents(value) == cents


@pytest.mark.parametrize("value", ["", "abc", "-5", "0", "12.345", "1e3"])
def test_invalid_prices_are_refused(value):
    assert parse_price_to_cents(value) is None


def test_whole_numbers_must_be_inside_the_range():
    assert parse_int("5", 0, 10) == 5
    assert parse_int("11", 0, 10) is None
    assert parse_int("-1", 0, 10) is None
    assert parse_int("", 0, 10) is None


def test_an_empty_product_form_reports_every_problem():
    _, errors = validate_product_form(MultiDict(), "vehicle")

    assert len(errors) >= 6  # name, price, stock, vehicle type, engine, horsepower


@pytest.mark.parametrize("filename", ["../../evil.jpg", "a/b.jpg", "photo.exe", "PHOTO.JPG"])
def test_unsafe_image_names_are_refused(filename):
    _, errors = validate_product_form(MultiDict({**GEAR_FORM, "image_filename": filename}), "gear")

    assert errors
