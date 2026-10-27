from flask import Blueprint, Response, current_app, render_template, url_for

from app.models import Product

bp = Blueprint("seo", __name__)


@bp.get("/sitemap.xml")
def sitemap():
    site = current_app.config["SITE_URL"]
    urls = [f"{site}/"] + [
        f"{site}/product/{p.slug}" for p in Product.query.order_by(Product.id).all()
    ]
    xml = render_template("sitemap.xml", urls=urls)
    return Response(xml, mimetype="application/xml")


@bp.get("/robots.txt")
def robots():
    site = current_app.config["SITE_URL"]
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /cart",
        "Disallow: /checkout",
        "Disallow: /orders",
        "Disallow: /documents",
        "Disallow: /login",
        "Disallow: /register",
        "",
        f"Sitemap: {site}/sitemap.xml",
        "",
    ]
    return Response("\n".join(lines), mimetype="text/plain")