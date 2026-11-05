from flask import Blueprint, abort, current_app, render_template, request

from app.catalog import CATEGORIES, MAX_QUERY_LENGTH, products_in_category, search_products
from app.models import Product, VehicleProduct

bp = Blueprint("main", __name__)

FEATURED_COUNT = 4


def product_structured_data(product) -> dict:
    """schema.org Product, used for Google rich results."""
    site = current_app.config["SITE_URL"]
    image_path = current_app.extensions["product_image_path"](product)
    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": product.description or product.get_technical_summary(),
        "image": f"{site}{image_path}",
        "sku": str(product.id),
        "offers": {
            "@type": "Offer",
            "url": f"{site}/product/{product.slug}",
            "priceCurrency": "EUR",
            "price": f"{product.price_cents / 100:.2f}",
            "availability": "https://schema.org/InStock"
            if product.stock > 0
            else "https://schema.org/OutOfStock",
        },
    }


@bp.get("/")
def index():
    products = Product.query.order_by(Product.name).all()
    featured = VehicleProduct.query.order_by(VehicleProduct.name).limit(FEATURED_COUNT).all()

    tiles = []
    for key, info in CATEGORIES.items():
        query = products_in_category(key)
        sample = query.first()
        if sample is not None:
            tiles.append(
                {"key": key, "label": info["label"], "product": sample, "count": query.count()}
            )

    return render_template("index.html", products=products, featured=featured, tiles=tiles)


@bp.get("/category/<key>")
def category(key):
    if key not in CATEGORIES:
        abort(404)
    products = products_in_category(key).all()
    return render_template("category.html", products=products, info=CATEGORIES[key])


@bp.get("/search")
def search():
    text = request.args.get("q", "").strip()[:MAX_QUERY_LENGTH]
    return render_template("search.html", products=search_products(text), q=text)


def breadcrumb_structured_data(product, category: dict) -> dict:
    """schema.org BreadcrumbList: Shop > Category > Product, with absolute URLs."""
    site = current_app.config["SITE_URL"]
    trail = [
        ("Shop", f"{site}/"),
        (category["label"], f"{site}/category/{product.category_key}"),
        (product.name, f"{site}/product/{product.slug}"),
    ]
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": position, "name": name, "item": url}
            for position, (name, url) in enumerate(trail, start=1)
        ],
    }


@bp.get("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    category = CATEGORIES[product.category_key]
    return render_template(
        "product.html",
        product=product,
        category=category,
        structured_data=product_structured_data(product),
        breadcrumb_data=breadcrumb_structured_data(product, category),
    )