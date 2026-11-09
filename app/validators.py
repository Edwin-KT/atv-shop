"""Server-side checks for what users type in forms. The browser checks some of this
too (required, type="email"...), but a user can skip the browser, so the server
always checks again."""

import re
import unicodedata
from decimal import Decimal

from email_validator import EmailNotValidError, validate_email

PHONE_PATTERN = re.compile(r"[0-9]{10}")
MIN_PASSWORD_LENGTH = 8

# A price: 1-7 digits, then optionally "." or "," and 1-2 decimals (189, 189.5, 189,50).
PRICE_PATTERN = re.compile(r"[0-9]{1,7}([.,][0-9]{1,2})?")
WHOLE_NUMBER_PATTERN = re.compile(r"[0-9]{1,9}")
# Only a plain file name: no folders, no "..", only common image extensions.
IMAGE_NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*\.(jpg|jpeg|png|webp)")
VEHICLE_TYPES = ("atv", "enduro")
# Text limits of the product form; the form's maxlength attributes use them too.
MIN_NAME_LENGTH = 3
MAX_NAME_LENGTH = 150
MAX_DESCRIPTION_LENGTH = 2000
MAX_GEAR_SIZE_LENGTH = 10


# ---------- accounts ----------


def is_valid_email(value: str) -> bool:
    """True if the value is a syntactically valid email address."""
    try:
        validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        return False
    return True


def is_valid_phone(value: str) -> bool:
    """True only for exactly 10 ASCII digits (e.g. 0712345678)."""
    return PHONE_PATTERN.fullmatch(value) is not None


def is_valid_password(value: str) -> bool:
    return len(value) >= MIN_PASSWORD_LENGTH


# ---------- the admin's product form ----------


def slugify(text: str) -> str:
    """The product's part of the URL: 'KTM 250 EXC-F' -> 'ktm-250-exc-f' (accents removed)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:150]


def parse_price_to_cents(value: str) -> int | None:
    """'189.50' or '189,5' -> 18950. None if the text is not a positive price.
    Decimal is exact (with float, 0.1 + 0.2 is 0.30000000000000004)."""
    value = value.strip()
    if not PRICE_PATTERN.fullmatch(value):
        return None
    cents = int(Decimal(value.replace(",", ".")) * 100)
    return cents if cents > 0 else None


def parse_int(value: str, minimum: int, maximum: int) -> int | None:
    """A whole number between minimum and maximum, or None."""
    value = value.strip()
    if not WHOLE_NUMBER_PATTERN.fullmatch(value):
        return None
    number = int(value)
    return number if minimum <= number <= maximum else None


def validate_product_form(form, product_type: str):
    """Check the product form. Returns (clean_values, errors); clean_values uses the
    model's column names, so it can be passed straight to the model."""
    errors = []
    clean = {}

    clean["name"] = form.get("name", "").strip()
    if not MIN_NAME_LENGTH <= len(clean["name"]) <= MAX_NAME_LENGTH:
        errors.append(f"Name must have between {MIN_NAME_LENGTH} and {MAX_NAME_LENGTH} characters.")
    elif not slugify(clean["name"]):
        errors.append("Name must contain letters or digits.")

    clean["description"] = form.get("description", "").strip()
    if len(clean["description"]) > MAX_DESCRIPTION_LENGTH:
        errors.append(f"Description is limited to {MAX_DESCRIPTION_LENGTH} characters.")

    clean["price_cents"] = parse_price_to_cents(form.get("price", ""))
    if clean["price_cents"] is None:
        errors.append("Price must be a positive number such as 189.00 (max 2 decimals).")

    clean["stock"] = parse_int(form.get("stock", ""), 0, 100_000)
    if clean["stock"] is None:
        errors.append("Stock must be a whole number between 0 and 100000.")

    image = form.get("image_filename", "").strip()
    if image and not IMAGE_NAME_PATTERN.fullmatch(image):
        errors.append("Image must be a lowercase file name ending in .jpg, .jpeg, .png or .webp.")
    clean["image_filename"] = image or None

    if product_type == "vehicle":
        clean["vehicle_type"] = form.get("vehicle_type", "")
        if clean["vehicle_type"] not in VEHICLE_TYPES:
            errors.append("Vehicle type must be ATV or enduro.")
        clean["engine_cc"] = parse_int(form.get("engine_cc", ""), 1, 5000)
        if clean["engine_cc"] is None:
            errors.append("Engine size must be between 1 and 5000 cc.")
        clean["horsepower"] = parse_int(form.get("horsepower", ""), 1, 500)
        if clean["horsepower"] is None:
            errors.append("Horsepower must be between 1 and 500.")
        clean["is_street_legal"] = form.get("is_street_legal") == "on"  # an unticked box sends nothing
    else:
        clean["gear_size"] = form.get("gear_size", "").strip()
        if not 1 <= len(clean["gear_size"]) <= MAX_GEAR_SIZE_LENGTH:
            errors.append(f"Size must have between 1 and {MAX_GEAR_SIZE_LENGTH} characters.")

    return clean, errors
