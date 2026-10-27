import json
import re
import xml.etree.ElementTree as ET

import pytest

from app.seed import seed_products

def compact(html: str) -> str:
    """Collapse whitespace so tests do not depend on how the HTML is formatted."""
    html = re.sub(r"\s+", " ", html)
    return html.replace(" />", "/>").replace("/>", " />")


@pytest.fixture()
def seeded(app):
    with app.app_context():
        seed_products()
    return app


def test_each_public_page_has_a_unique_title_and_description(seeded, client):
    pages = ["/", "/product/ktm-250-exc-f", "/product/enduro-helmet-pro"]
    titles, descriptions = set(), set()

    for url in pages:
        html = compact(client.get(url).get_data(as_text=True))
        titles.add(re.search(r"<title>(.*?)</title>", html, re.S).group(1).strip())
        descriptions.add(re.search(r'name="description" content="(.*?)"', html, re.S).group(1))

    assert len(titles) == len(pages)
    assert len(descriptions) == len(pages)


def test_descriptions_have_a_reasonable_length(seeded, client):
    html = compact(client.get("/product/ktm-250-exc-f").get_data(as_text=True))

    description = re.search(r'name="description" content="(.*?)"', html, re.S).group(1)

    assert 50 <= len(description) <= 200


def test_canonical_and_open_graph_tags(seeded, client):
    html = compact(client.get("/product/ktm-250-exc-f").get_data(as_text=True))

    assert 'rel="canonical" href="http://127.0.0.1:5000/product/ktm-250-exc-f"' in html
    assert 'property="og:title" content="KTM 250 EXC-F"' in html
    assert 'property="og:image"' in html


def test_product_has_valid_structured_data(seeded, client):
    html = client.get("/product/ktm-250-exc-f").get_data(as_text=True)

    raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
    data = json.loads(raw)

    assert data["@type"] == "Product"
    assert data["name"] == "KTM 250 EXC-F"
    assert data["offers"]["price"] == "10999.00"
    assert data["offers"]["priceCurrency"] == "EUR"
    assert data["offers"]["availability"].endswith("InStock")


def test_structured_data_cannot_break_out_of_its_script_tag(seeded, app, client):
    from app.extensions import db
    from app.models import Product

    with app.app_context():
        product = Product.query.filter_by(slug="ktm-250-exc-f").one()
        product.description = "</script><script>alert(1)</script>"
        db.session.commit()

    html = client.get("/product/ktm-250-exc-f").get_data(as_text=True)

    assert "</script><script>alert(1)" not in html


def test_sitemap_lists_the_catalog(seeded, client):
    response = client.get("/sitemap.xml")

    assert response.mimetype == "application/xml"
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [e.text for e in ET.fromstring(response.data).findall("s:url/s:loc", namespace)]
    assert "http://127.0.0.1:5000/" in urls
    assert "http://127.0.0.1:5000/product/ktm-250-exc-f" in urls
    assert len(urls) == 7  # home + 6 products
    assert not any("/admin" in u or "/cart" in u for u in urls)


def test_robots_txt_blocks_private_areas_and_points_to_the_sitemap(client):
    response = client.get("/robots.txt")
    text = response.get_data(as_text=True)

    assert response.mimetype == "text/plain"
    assert "Disallow: /admin/" in text
    assert "Sitemap: http://127.0.0.1:5000/sitemap.xml" in text
    assert "Disallow: /\n" not in text  # the public pages must stay crawlable


def test_private_pages_are_noindex_and_public_pages_are_not(seeded, client):
    assert "noindex" in client.get("/login").headers["X-Robots-Tag"]
    assert "noindex" in client.get("/cart").headers["X-Robots-Tag"]
    assert "X-Robots-Tag" not in client.get("/").headers
    assert "X-Robots-Tag" not in client.get("/product/ktm-250-exc-f").headers


def test_sitemap_uses_the_configured_site_url_not_the_host_header(seeded, client):
    text = client.get("/sitemap.xml", headers={"Host": "evil.example"}).get_data(as_text=True)

    assert "evil.example" not in text


def test_links_and_images_have_descriptive_labels(seeded, client):
    html = client.get("/").get_data(as_text=True)

    assert 'aria-label="View KTM 250 EXC-F"' in html
    assert 'alt="KTM 250 EXC-F"' in html