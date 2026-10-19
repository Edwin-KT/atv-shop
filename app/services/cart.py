from dataclasses import dataclass

from flask import session

from app.models import Product
from app.money import format_price

CART_SESSION_KEY = "cart"
MAX_QUANTITY_PER_ITEM = 10


@dataclass
class CartLine:
    product: Product
    quantity: int

    @property
    def line_total_cents(self) -> int:
        return self.product.price_cents * self.quantity

    @property
    def line_total_display(self) -> str:
        return format_price(self.line_total_cents)


def _read_cart() -> dict[str, int]:
    return session.get(CART_SESSION_KEY, {})


def _save_cart(cart: dict[str, int]) -> None:
    # Assigning a NEW dict makes Flask notice the session changed.
    session[CART_SESSION_KEY] = cart


def _max_allowed(product: Product) -> int:
    return min(product.stock, MAX_QUANTITY_PER_ITEM)


def add_item(product: Product, quantity: int = 1) -> int:
    """Add to the cart; returns the quantity now in the cart (0 = not added)."""
    cart = dict(_read_cart())
    key = str(product.id)
    new_quantity = min(cart.get(key, 0) + max(quantity, 1), _max_allowed(product))

    if new_quantity <= 0:  # out of stock
        cart.pop(key, None)
    else:
        cart[key] = new_quantity
    _save_cart(cart)
    return max(new_quantity, 0)


def set_quantity(product: Product, quantity: int) -> int:
    """Set an exact quantity; 0 or less removes the product."""
    cart = dict(_read_cart())
    key = str(product.id)
    new_quantity = min(quantity, _max_allowed(product))

    if new_quantity <= 0:
        cart.pop(key, None)
    else:
        cart[key] = new_quantity
    _save_cart(cart)
    return max(new_quantity, 0)


def remove_item(product_id: int) -> None:
    cart = dict(_read_cart())
    cart.pop(str(product_id), None)
    _save_cart(cart)


def clear_cart() -> None:
    session.pop(CART_SESSION_KEY, None)


def cart_item_count() -> int:
    return sum(_read_cart().values())


def get_cart_lines() -> list[CartLine]:
    """Load the products in the cart from the database (prices are always fresh)."""
    cart = _read_cart()
    if not cart:
        return []

    ids = [int(key) for key in cart]
    products = Product.query.filter(Product.id.in_(ids)).all()
    by_id = {product.id: product for product in products}

    # Drop products that no longer exist in the catalog.
    if len(by_id) != len(ids):
        _save_cart({str(pid): cart[str(pid)] for pid in ids if pid in by_id})

    lines = [CartLine(by_id[pid], cart[str(pid)]) for pid in ids if pid in by_id]
    return sorted(lines, key=lambda line: line.product.name)


def cart_total_cents(lines: list[CartLine]) -> int:
    return sum(line.line_total_cents for line in lines)