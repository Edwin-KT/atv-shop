"""INTEGRATION tests: what search engines see.

Rubric: N8.01 SEO (own title and description on every page, one h1, lang, alt
texts, robots.txt and sitemap.xml); the Lighthouse score itself is measured on
the published site."""

import re
import xml.etree.ElementTree as ET

import pytest

from app.routes.main import CATEGORIES
from app.cli import seed_products

SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@pytest.fixture()
def seeded(app):
    with app.app_context():
        seed_products()
    return app


def title_and_description(html):
    html = re.sub(r"\s+", " ", html)  # the templates may wrap lines anywhere
    title = re.search(r"<title>(.*?)</title>", html).group(1).strip()
    description = re.search(r'name="description" content="(.*?)"', html).group(1)
    return title, description


def sitemap_urls(client, **kwargs):
    response = client.get("/sitemap.xml", **kwargs)
    assert response.mimetype == "application/xml"
    return [e.text for e in ET.fromstring(response.data).findall("s:url/s:loc", SITEMAP_NS)]


def test_each_public_page_has_its_own_title_and_description(seeded, client):
    pages = ["/", "/category/gear", "/product/ktm-250-exc-f", "/product/enduro-helmet-pro"]
    found = [title_and_description(client.get(url).get_data(as_text=True)) for url in pages]

    assert len({title for title, _ in found}) == len(pages)
    assert len({description for _, description in found}) == len(pages)


def test_descriptions_have_a_reasonable_length(seeded, client):
    _, description = title_and_description(client.get("/product/ktm-250-exc-f").get_data(as_text=True))

    assert 50 <= len(description) <= 200


@pytest.mark.parametrize("with_products", [False, True])
def test_the_home_page_has_exactly_one_h1(app, client, with_products):
    if with_products:
        with app.app_context():
            seed_products()

    assert client.get("/").get_data(as_text=True).count("<h1") == 1


def test_pages_declare_their_language(client):
    assert '<html lang="en">' in client.get("/").get_data(as_text=True)


def test_links_and_images_have_descriptive_labels(seeded, client):
    html = client.get("/").get_data(as_text=True)

    assert 'aria-label="View KTM 250 EXC-F"' in html
    assert 'alt="KTM 250 EXC-F"' in html
    assert not re.search(r"<img(?![^>]*\balt=)[^>]*>", html)  # every image has an alt


def test_sitemap_lists_home_categories_and_products(seeded, client):
    urls = sitemap_urls(client)

    assert "http://localhost/" in urls
    for key in CATEGORIES:
        assert f"http://localhost/category/{key}" in urls
    assert "http://localhost/product/ktm-250-exc-f" in urls
    assert len(urls) == 10  # home + 3 categories + 6 products
    assert not any(private in url for url in urls for private in ("/admin", "/cart", "/search"))


def test_sitemap_uses_https_behind_the_proxy(seeded, client):
    """On Render the proxy says the visitor used HTTPS (ProxyFix reads X-Forwarded-Proto)."""
    urls = sitemap_urls(client, headers={"X-Forwarded-Proto": "https"})

    assert all(url.startswith("https://") for url in urls)


def test_robots_txt_blocks_private_areas_and_points_to_the_sitemap(client):
    response = client.get("/robots.txt")
    lines = response.get_data(as_text=True).splitlines()

    assert response.mimetype == "text/plain"
    assert lines[0] == "User-agent: *"
    for path in ("/admin/", "/cart", "/checkout", "/login", "/search"):
        assert f"Disallow: {path}" in lines
    assert "Disallow: /" not in lines  # the public pages must stay crawlable
    assert "Sitemap: http://localhost/sitemap.xml" in lines
