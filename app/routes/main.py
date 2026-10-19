from flask import Blueprint, render_template

from app.models import Product

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    products = Product.query.order_by(Product.name).all()
    return render_template("index.html", products=products)


@bp.get("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    return render_template("product.html", product=product)