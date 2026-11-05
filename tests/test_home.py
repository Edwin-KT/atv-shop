"""Home page: campaign banner, featured band, category tiles, product cards, performance."""

import re
from pathlib import Path

import pytest

from app.catalog import CATEGORIES, products_in_category
from app.models import GearProduct, VehicleProduct
from app.seed import seed_products

ROOT = Path(__file__).resolve().parent.parent
ANIMATIONS = (ROOT / "app" / "static" / "css" / "animations.css").read_text(encoding="utf-8")


@pytest.fixture()
def seeded(app):
    with app.app_context():
        seed_products()
    return app


def home(client):
    return client.get("/").get_data(as_text=True)


def banner(html):
    return re.search(r'<section class="hero-banner".*?</section>', html, re.S).group(0)


def card_for(html, slug):
    for card in re.findall(r'<article class="product-card">.*?</article>', html, re.S):
        if f"/product/{slug}" in card:
            return card
    raise AssertionError(f"no card for {slug}")


# --- headings ---


@pytest.mark.parametrize("with_products", [False, True])
def test_home_has_exactly_one_h1_the_banner_title(app, client, with_products):
    if with_products:
        with app.app_context():
            seed_products()
    html = home(client)

    assert re.findall(r"<h1\b[^>]*>(.*?)</h1>", html, re.S) == ["Ready for the trail"]
    assert re.search(r'<h2 id="catalog-title" class="section-title">Catalog</h2>', html)


# --- campaign banner ---


def test_banner_button_goes_to_the_enduro_category(client):
    html = banner(home(client))

    assert re.search(r'href="/category/enduro"\s*>Shop enduro bikes</a', html)
    assert client.get("/category/enduro").status_code == 200


def test_banner_photo_is_a_sized_high_priority_webp(client):
    img = re.search(r"<img\b[^>]*>", banner(home(client)), re.S).group(0)

    assert 'width="1920"' in img and 'height="1536"' in img  # no layout shift
    assert 'fetchpriority="high"' in img
    assert 'loading="lazy"' not in img  # it is the largest thing above the fold
    assert "img/hero/trail-960.webp 960w" in img
    assert "img/hero/trail-1920.webp 1920w" in img
    assert re.search(r'alt="[^"]{10,}"', img)


@pytest.mark.parametrize("name", ["trail-960.webp", "trail-1920.webp"])
def test_banner_photos_are_small_webp_files(client, name):
    response = client.get(f"/static/img/hero/{name}")

    assert response.status_code == 200
    assert response.mimetype == "image/webp"
    assert len(response.data) < 200 * 1024


def test_banner_photo_is_preloaded_only_on_the_home_page(seeded, client):
    preload = re.compile(r'<link\s+rel="preload"\s+as="image"[^>]*trail-1920\.webp', re.S)

    assert preload.search(home(client))
    for url in ["/category/atv", "/search?q=ktm", "/product/ktm-250-exc-f", "/cart", "/login"]:
        assert not preload.search(client.get(url).get_data(as_text=True)), url


# --- animation (rubric: at least one animation) ---


def test_animation_exists_and_is_switched_off_for_reduced_motion():
    assert "@keyframes" in ANIMATIONS
    reduced = ANIMATIONS.split("@media (prefers-reduced-motion: reduce)")[1]
    assert "animation: none !important" in reduced
    assert "transition: none !important" in reduced


# --- featured band (the image carousel) ---


def test_featured_band_shows_price_and_specs_from_the_database(seeded, client):
    html = home(client)
    band = re.search(r'id="heroCarousel".*?</section>', html, re.S).group(0)
    with seeded.app_context():
        ktm = VehicleProduct.query.filter_by(slug="ktm-250-exc-f").one()
        whole, cc = f"{ktm.price_cents // 100:,}", ktm.engine_cc

    assert "<h2 class=\"featured-title\">Featured vehicles</h2>" in band
    assert f'<span class="price-whole">{whole}</span><span class="price-rest">.00 EUR</span>' in band
    assert f'<span class="plate-number">{cc}</span>' in band  # real engine size, not the model name


# --- category tiles ---


def test_tiles_show_the_real_number_of_products(seeded, client):
    html = re.search(
        r'aria-labelledby="categories-title".*?</section>', home(client), re.S
    ).group(0)

    with seeded.app_context():
        expected = {key: products_in_category(key).count() for key in CATEGORIES}
    for key, count in expected.items():
        tile = re.search(rf'href="/category/{key}"\s*>.*?</a>', html, re.S).group(0)
        word = "product" if count == 1 else "products"
        assert f">{count} {word}</span" in tile


def test_tile_label_sits_below_the_photo_not_over_it(seeded, client):
    """Regression: on phones the name ("Enduro bikes") overlapped the photo."""
    section = re.search(
        r'aria-labelledby="categories-title".*?</section>', home(client), re.S
    ).group(0)
    for tile in re.findall(r'<a\s+class="category-tile".*?</a>', section, re.S):
        assert tile.index('class="ratio tile-ratio"') < tile.index('class="category-tile-label"')

    pages = (ROOT / "app" / "static" / "css" / "pages.css").read_text(encoding="utf-8")
    rule = re.search(r"\.category-tile-label\s*\{([^}]*)\}", pages).group(1)
    assert "position: absolute" not in rule


def test_tiles_have_no_sequence_numbers(seeded, client):
    section = re.search(
        r'aria-labelledby="categories-title".*?</section>', home(client), re.S
    ).group(0)

    assert not re.search(r">\s*0[1-9]\s*<", section)


# --- product cards ---


def test_vehicle_cards_show_engine_power_and_road_use(seeded, client):
    html = home(client)
    with seeded.app_context():
        vehicles = [
            (v.slug, v.engine_cc, v.horsepower, v.is_street_legal) for v in VehicleProduct.query.all()
        ]

    for slug, cc, hp, legal in vehicles:
        card = card_for(html, slug)
        assert f'<span class="plate-number">{cc}</span><span class="plate-unit">cc</span>' in card
        assert f'<li class="spec">{hp} hp</li>' in card
        road = "Street legal" if legal else "Off-road only"
        assert f'<li class="spec">{road}</li>' in card


def test_gear_cards_show_the_size(seeded, client):
    html = home(client)
    with seeded.app_context():
        gear = [(g.slug, g.gear_size) for g in GearProduct.query.all()]

    for slug, size in gear:
        card = card_for(html, slug)
        assert f'<li class="spec">Size {size}</li>' in card
        assert "plate" not in card


def test_card_price_has_small_decimals(seeded, client):
    card = card_for(home(client), "enduro-helmet-pro")

    assert re.search(
        r'<p class="product-price"><span class="price"><span class="price-whole">189</span>'
        r'<span class="price-rest">\.00 EUR</span></span></p>',
        card,
    )


def test_quick_add_button_has_an_icon_and_a_label(seeded, client):
    card = card_for(home(client), "enduro-helmet-pro")
    button = re.search(r'<button\s+class="quick-add-btn".*?</button>', card, re.S).group(0)

    assert 'aria-label="Add Enduro Helmet Pro to cart"' in button
    assert "icon-plus-lg" in button


def test_images_below_the_banner_load_lazily(seeded, client):
    html = home(client)
    below = html.split('<section class="hero-banner"')[1].split("</section>", 1)[1]
    images = re.findall(r"<img\b[^>]*>", below, re.S)

    assert images
    assert all('loading="lazy"' in img for img in images)
