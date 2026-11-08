from flask import Blueprint, Response, abort, render_template, request, url_for

from app.models import GearProduct, Product, VehicleProduct

bp = Blueprint("main", __name__)

FEATURED_COUNT = 4  # vehicles in the home page carousel

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


@bp.get("/")
def index():
    products = Product.query.order_by(Product.name).all()
    featured = VehicleProduct.query.order_by(VehicleProduct.name).limit(FEATURED_COUNT).all()
    return render_template("index.html", products=products, featured=featured)


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


@bp.get("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    category = CATEGORIES[product.category_key]
    return render_template("product.html", product=product, category=category)


# --- SEO: files for search engines ---


@bp.get("/sitemap.xml")
def sitemap():
    """Every public page, so search engines find all products."""
    # _external=True gives full URLs (https://... behind Render's proxy, thanks to ProxyFix).
    urls = [url_for("main.index", _external=True)]
    urls += [url_for("main.category", key=key, _external=True) for key in CATEGORIES]
    urls += [
        url_for("main.product_detail", slug=product.slug, _external=True)
        for product in Product.query.order_by(Product.id)
    ]
    return Response(render_template("sitemap.xml", urls=urls), mimetype="application/xml")


@bp.get("/robots.txt")
def robots():
    """Search engines may read the shop, but not the private pages."""
    private = ["/admin/", "/cart", "/checkout", "/orders", "/documents", "/login", "/register", "/search"]
    lines = ["User-agent: *"] + [f"Disallow: {path}" for path in private]
    lines += ["", f"Sitemap: {url_for('main.sitemap', _external=True)}", ""]
    return Response("\n".join(lines), mimetype="text/plain")