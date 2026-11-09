from flask import Blueprint, Response, abort, render_template, request, url_for

from app.models import Product, VehicleProduct
from app.services.cart import max_allowed
from app.services.catalog import CATEGORIES, clean_query, products_in_category, search_products

bp = Blueprint("main", __name__)

FEATURED_COUNT = 4  # vehicles in the home page carousel


@bp.get("/")
def index():
    products = Product.query.order_by(Product.name).all()
    featured = VehicleProduct.query.order_by(VehicleProduct.name).limit(FEATURED_COUNT).all()
    return render_template("index.html", products=products, featured=featured)


@bp.get("/category/<key>")
def category(key):
    if key not in CATEGORIES:
        abort(404)
    products = products_in_category(key)
    return render_template("category.html", products=products, info=CATEGORIES[key])


@bp.get("/search")
def search():
    q = clean_query(request.args.get("q", ""))
    return render_template("search.html", products=search_products(q), q=q)


@bp.get("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    category = CATEGORIES[product.category_key]
    return render_template(
        "product.html", product=product, category=category, max_quantity=max_allowed(product)
    )


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