from flask import Blueprint, render_template

from app.models import Product, VehicleProduct

bp = Blueprint("main", __name__)

FEATURED_COUNT = 4

from flask import current_app, url_for

def product_structured_data(product) -> dict:
    """schema.org Product, used for Google rich results."""
    site = current_app.config["SITE_URL"]
    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": product.description or product.get_technical_summary(),
        "image": f"{site}{current_app.extensions["product_image_path"](product)}",
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
    return render_template("index.html", products=products, featured=featured)


@bp.get("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    return render_template(
        "product.html", product=product, structured_data=product_structured_data(product)
    )