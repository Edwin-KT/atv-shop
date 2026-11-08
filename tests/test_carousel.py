import re

from app.models import VehicleProduct
from app.cli import seed_products


def seed(app):
    with app.app_context():
        seed_products()


def count(pattern, html):
    return len(re.findall(pattern, html))


def test_carousel_shows_every_featured_vehicle(app, client):
    seed(app)

    html = client.get("/").get_data(as_text=True)

    assert count(r"carousel-item(?![-\w])", html) == 3  # the seed has 3 vehicles
    assert count(r"data-bs-slide-to=", html) == 3


def test_exactly_one_slide_is_active(app, client):
    seed(app)

    html = client.get("/").get_data(as_text=True)

    assert count(r"carousel-item active", html) == 1


def test_only_vehicles_are_featured(app, client):
    seed(app)

    html = client.get("/").get_data(as_text=True)
    hero = html.split('id="heroCarousel"')[1].split("</section>")[0]

    assert "KTM 250 EXC-F" in hero
    assert "Enduro Helmet Pro" not in hero


def test_slides_have_alt_text_and_a_link_to_the_product(app, client):
    seed(app)

    html = client.get("/").get_data(as_text=True)
    hero = html.split('id="heroCarousel"')[1].split("</section>")[0]

    assert 'alt="KTM 250 EXC-F"' in hero
    assert "/product/ktm-250-exc-f" in hero


def test_controls_are_accessible(app, client):
    seed(app)

    html = client.get("/").get_data(as_text=True)

    assert "Previous" in html and "Next" in html
    assert 'aria-label="Featured vehicles"' in html


def test_carousel_is_hidden_when_there_are_no_vehicles(client):
    html = client.get("/").get_data(as_text=True)

    assert "heroCarousel" not in html

def test_slides_show_price_and_specs_from_the_database(app, client):
    seed(app)
    with app.app_context():
        ktm = VehicleProduct.query.filter_by(slug="ktm-250-exc-f").one()
        price, summary = f"{ktm.price_cents // 100:,}.00 EUR", ktm.get_technical_summary()

    hero = client.get("/").get_data(as_text=True).split('id="heroCarousel"')[1].split("</section>")[0]

    assert f'<p class="hero-price">{price}</p>' in hero
    assert f'<p class="product-specs">{summary}</p>' in hero
