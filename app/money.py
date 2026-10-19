def format_price(cents: int) -> str:
    """Format an amount stored in cents, e.g. 1299900 -> '12,999.00 EUR'."""
    return f"{cents / 100:,.2f} EUR"