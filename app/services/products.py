import re
import unicodedata
from typing import Mapping

from app.extensions import db
from app.models import GearProduct, Product, VehicleProduct

PRODUCT_CLASSES = {"vehicle": VehicleProduct, "gear": GearProduct}
VEHICLE_TYPES = ("atv", "enduro")

PRICE_PATTERN = re.compile(r"[0-9]{1,7}([.,][0-9]{1,2})?")
INTEGER_PATTERN = re.compile(r"[0-9]{1,9}")
# Only a plain file name: no folders, no "..", only common image extensions.
IMAGE_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*\.(jpg|jpeg|png|webp)")


def slugify(text: str) -> str:
    """'KTM 250 EXC-F' -> 'ktm-250-exc-f' (accents removed)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:150]


def parse_price_to_cents(value: str) -> int | None:
    """'189.50' or '189,5' -> 18950. None if invalid or zero. No floats involved."""
    value = value.strip()
    if not PRICE_PATTERN.fullmatch(value):
        return None
    whole, _, fraction = value.replace(",", ".").partition(".")
    cents = int(whole) * 100 + int(fraction.ljust(2, "0") or 0)
    return cents if cents > 0 else None


def parse_int(value: str, minimum: int, maximum: int) -> int | None:
    value = value.strip()
    if not INTEGER_PATTERN.fullmatch(value):
        return None
    number = int(value)
    return number if minimum <= number <= maximum else None


def validate_product_form(form: Mapping[str, str], product_type: str):
    """Return (clean_values, errors). clean_values uses model attribute names."""
    errors: list[str] = []
    clean: dict = {}

    name = form.get("name", "").strip()
    if not 3 <= len(name) <= 150:
        errors.append("Name must have between 3 and 150 characters.")
    elif not slugify(name):
        errors.append("Name must contain letters or digits.")
    clean["name"] = name

    description = form.get("description", "").strip()
    if len(description) > 2000:
        errors.append("Description is limited to 2000 characters.")
    clean["description"] = description

    price_cents = parse_price_to_cents(form.get("price", ""))
    if price_cents is None:
        errors.append("Price must be a positive number such as 189.00 (max 2 decimals).")
    clean["price_cents"] = price_cents

    stock = parse_int(form.get("stock", ""), 0, 100_000)
    if stock is None:
        errors.append("Stock must be a whole number between 0 and 100000.")
    clean["stock"] = stock

    image = form.get("image_filename", "").strip()
    if image and not IMAGE_PATTERN.fullmatch(image):
        errors.append(
            "Image must be a lowercase file name ending in .jpg, .jpeg, .png or .webp."
        )
    clean["image_filename"] = image or None

    if product_type == "vehicle":
        vehicle_type = form.get("vehicle_type", "")
        if vehicle_type not in VEHICLE_TYPES:
            errors.append("Vehicle type must be ATV or enduro.")
        clean["vehicle_type"] = vehicle_type

        engine_cc = parse_int(form.get("engine_cc", ""), 1, 5000)
        if engine_cc is None:
            errors.append("Engine size must be between 1 and 5000 cc.")
        clean["engine_cc"] = engine_cc

        horsepower = parse_int(form.get("horsepower", ""), 1, 500)
        if horsepower is None:
            errors.append("Horsepower must be between 1 and 500.")
        clean["horsepower"] = horsepower

        clean["is_street_legal"] = form.get("is_street_legal") == "on"
    else:
        gear_size = form.get("gear_size", "").strip()
        if not 1 <= len(gear_size) <= 10:
            errors.append("Size must have between 1 and 10 characters.")
        clean["gear_size"] = gear_size

    return clean, errors


def unique_slug(name: str) -> str:
    base = slugify(name)
    slug, counter = base, 2
    while Product.query.filter_by(slug=slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def create_product(product_type: str, clean: dict) -> Product:
    product = PRODUCT_CLASSES[product_type](slug=unique_slug(clean["name"]), **clean)
    db.session.add(product)
    db.session.commit()
    return product


def update_product(product: Product, clean: dict) -> Product:
    """The slug is intentionally NOT updated, so existing links keep working."""
    for key, value in clean.items():
        setattr(product, key, value)
    db.session.commit()
    return product