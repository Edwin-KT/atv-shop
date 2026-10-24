from flask import Blueprint, render_template

from app.models import Product, VehicleProduct

bp = Blueprint("main", __name__)

FEATURED_COUNT = 4


@bp.get("/")
def index():
    products = Product.query.order_by(Product.name).all()
    featured = VehicleProduct.query.order_by(VehicleProduct.name).limit(FEATURED_COUNT).all()
    return render_template("index.html", products=products, featured=featured)


@bp.get("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    return render_template("product.html", product=product)