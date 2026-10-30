from app.models import GearProduct, Product, VehicleProduct

CATEGORIES = {
    "atv": {
        "label": "ATVs",
        "title": "ATVs for trails, work and adventure",
        "description": "Browse quad bikes for trail riding, farm work and road use, with engine size and power listed for each model.",
    },
    "enduro": {
        "label": "Enduro bikes",
        "title": "Enduro motorcycles",
        "description": "Lightweight enduro motorcycles for forest trails and hard enduro, from trail bikes to competition machines.",
    },
    "gear": {
        "label": "Riding gear",
        "title": "Helmets, boots, gloves and riding gear",
        "description": "Protective riding gear for off-road: helmets, boots, gloves and more, in sizes for every rider.",
    },
}

MAX_QUERY_LENGTH = 60


def products_in_category(key: str):
    """Query for one category. Raises KeyError for an unknown key."""
    if key == "gear":
        query = GearProduct.query
    elif key in ("atv", "enduro"):
        query = VehicleProduct.query.filter(VehicleProduct.vehicle_type == key)
    else:
        raise KeyError(key)
    return query.order_by(Product.name)


def search_products(text: str) -> list[Product]:
    """Case-insensitive search by name. % and _ typed by the user are escaped."""
    text = text.strip()[:MAX_QUERY_LENGTH]
    if not text:
        return []
    return (
        Product.query.filter(Product.name.icontains(text, autoescape=True))
        .order_by(Product.name)
        .all()
    )