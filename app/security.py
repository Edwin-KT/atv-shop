import pytest
from werkzeug.datastructures import MultiDict

from app.services.products import (
    parse_int,
    parse_price_to_cents,
    slugify,
    validate_product_form,
)

VEHICLE_FORM = {
    "name": "Yamaha Raptor 700",
    "description": "Sport ATV",
    "price": "8999.00",
    "stock": "3",
    "image_filename": "yamaha-raptor-700.jpg",
    "vehicle_type": "atv",
    "engine_cc": "686",
    "horsepower": "50",
    "is_street_legal": "on",
}
GEAR_FORM = {
    "name": "Trail Jacket",
    "description": "",
    "price": "129.90",
    "stock": "10",
    "image_filename": "",
    "gear_size": "L",
}


def test_slugify():
    assert slugify("KTM 250 EXC-F") == "ktm-250-exc-f"
    assert slugify("Cască Enduro  Pro!") == "casca-enduro-pro"
    assert slugify("!!!") == ""


@pytest.mark.parametrize(
    "value, expected",
    [("189", 18900), ("189.00", 18900), ("189,5", 18950), ("0.99", 99), (" 5.05 ", 505)],
)
def test_valid_prices(value, expected):
    assert parse_price_to_cents(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "-5", "0", "0.00", "1e3", "12.345", "1 000", "12.", ".5"])
def test_invalid_prices(value):
    assert parse_price_to_cents(value) is None


def test_parse_int_range():
    assert parse_int("5", 0, 10) == 5
    assert parse_int("11", 0, 10) is None
    assert parse_int("-1", 0, 10) is None
    assert parse_int("", 0, 10) is None


def test_valid_vehicle_form():
    clean, errors = validate_product_form(MultiDict(VEHICLE_FORM), "vehicle")

    assert errors == []
    assert clean["price_cents"] == 899_900
    assert clean["is_street_legal"] is True
    assert clean["engine_cc"] == 686


def test_valid_gear_form_needs_no_vehicle_fields():
    clean, errors = validate_product_form(MultiDict(GEAR_FORM), "gear")

    assert errors == []
    assert clean["gear_size"] == "L"
    assert clean["image_filename"] is None
    assert "engine_cc" not in clean


def test_empty_form_reports_every_problem():
    _, errors = validate_product_form(MultiDict(), "vehicle")

    assert len(errors) >= 6


@pytest.mark.parametrize("filename", ["../../evil.jpg", "a/b.jpg", "photo.exe", "PHOTO.JPG", ".jpg", "x.jpg.exe"])
def test_unsafe_image_names_are_rejected(filename):
    _, errors = validate_product_form(MultiDict({**GEAR_FORM, "image_filename": filename}), "gear")

    assert errors