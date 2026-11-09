"""The catalog: the shop's categories, the products in each one, and the search."""

from app.models import GearProduct, Product, VehicleProduct

# The shop's categories: key in the URL (/category/atv) -> texts for the page.
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

MAX_QUERY_LENGTH = 60  # also the search box's maxlength (base.html)


def products_in_category(key: str) -> list[Product]:
    """The products of one category, by name. `key` is one of CATEGORIES
    (the route answers 404 for any other key before calling this)."""
    if key == "gear":
        query = GearProduct.query
    else:  # "atv" or "enduro"
        query = VehicleProduct.query.filter(VehicleProduct.vehicle_type == key)
    return query.order_by(Product.name).all()


def clean_query(text: str) -> str:
    """The search text as it is searched for and shown: no outer spaces, at most
    MAX_QUERY_LENGTH characters (the only place where it is cut)."""
    return text.strip()[:MAX_QUERY_LENGTH]


def search_products(text: str) -> list[Product]:
    """Case-insensitive search by name, for a text already passed through clean_query.
    % and _ typed by the user are escaped, so they are searched for literally."""
    if not text:
        return []
    return (
        Product.query.filter(Product.name.icontains(text, autoescape=True))
        .order_by(Product.name)
        .all()
    )
