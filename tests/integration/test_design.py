"""INTEGRATION tests (pages through the app) and checks of the CSS files for the design.

Rubric: N4.03 image carousel; N4.04 animation (and it ends with the text visible);
N5.01 at least 2 CSS files and 10 different CSS properties; N5.02 responsive layout
(viewport, grid, folding navbar, media queries, tables that scroll)."""

import re
from pathlib import Path

from app.cli import seed_products
from app.models import VehicleProduct
from helpers import register_and_login

ROOT = Path(__file__).resolve().parents[2]  # the project folder
STATIC = ROOT / "app" / "static"
TEMPLATES = ROOT / "app" / "templates"
CSS_FILES = ["base.css", "layout.css", "animations.css"]


def css(name):
    return (STATIC / "css" / name).read_text(encoding="utf-8")


def page(client, url="/"):
    return client.get(url).get_data(as_text=True)


# --- N5.01: at least 2 CSS files and 10 distinct properties ---


def test_three_css_files_are_linked_from_general_to_specific(client):
    html = page(client)
    links = re.findall(r'href="/static/css/([\w-]+\.css)"', html)

    assert links == CSS_FILES
    assert sorted(p.name for p in (STATIC / "css").glob("*.css")) == sorted(CSS_FILES)


def test_css_uses_many_distinct_properties():
    properties = set()
    for name in CSS_FILES:
        properties |= set(re.findall(r"^\s+([a-z-]+)\s*:", css(name), re.M))

    assert len(properties) >= 10
    assert {"color", "background-color", "font-family", "padding", "display"} <= properties


def test_tokens_are_defined_only_in_base_css():
    assert ":root" in css("base.css")
    assert all(":root" not in css(name) for name in CSS_FILES[1:])


def test_templates_have_no_inline_styles_or_event_handlers():
    """The strict CSP blocks inline styles and handlers, so all styling lives in the CSS files."""
    for template in TEMPLATES.rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        assert 'style="' not in text, template.name
        assert not re.search(r"\son[a-z]+=", text), template.name


# --- N5.02: responsive ---


def test_every_page_has_the_viewport_meta(client):
    for url in ("/", "/login", "/register", "/cart", "/category/atv"):
        assert 'name="viewport" content="width=device-width, initial-scale=1"' in page(client, url)


def test_product_grid_has_1_2_or_3_columns_by_screen_size(app, client):
    with app.app_context():
        seed_products()

    assert 'class="row row-cols-1 row-cols-sm-2 row-cols-lg-3' in page(client)


def test_navbar_folds_into_a_menu_on_small_screens(client):
    html = page(client)

    assert 'class="navbar navbar-expand-lg sticky-top site-header"' in html
    assert re.search(r'class="navbar-toggler"[^>]*data-bs-target="#mainMenu"', html, re.S)
    assert 'class="collapse navbar-collapse" id="mainMenu"' in html


def test_navbar_is_sticky_with_the_bootstrap_class(client):
    """sticky-top is pure CSS (position: sticky). A sticky element only sticks inside its
    parent, so the <nav> must be a direct child of <body>, not wrapped in a <header>."""
    html = page(client)

    nav = re.search(r"<nav [^>]*>", html).group(0)
    assert "sticky-top" in nav.split('class="')[1].split('"')[0].split()
    assert re.search(r"<body>\s*<nav ", html)


def test_open_phone_menu_scrolls_when_taller_than_the_screen():
    phone = css("layout.css").split("@media (max-width: 991.98px)")[1].split("\n}\n")[0]
    rule = re.search(r"\.navbar-collapse\s*\{([^}]*)\}", phone).group(1)

    assert "max-height:" in rule
    assert "overflow-y: auto" in rule


def test_carousel_starts_below_the_sticky_navbar(app, client):
    with app.app_context():
        seed_products()
    html = page(client)

    # the carousel comes after the navbar, and outside <main> so it can use the full width
    assert html.index("</nav>") < html.index('id="heroCarousel"') < html.index("<main")
    # our CSS sets no z-index, so Bootstrap's sticky-top (z-index 1020) always stays
    # above the carousel controls (z-index 1-2) when the page scrolls under the navbar
    assert all("z-index" not in css(name) for name in CSS_FILES)
    assert "background-color: var(--color-surface)" in re.search(
        r"\.site-header\s*\{([^}]*)\}", css("layout.css")
    ).group(1)


def test_css_has_media_queries_for_phone_and_desktop():
    layout = css("layout.css")

    assert "@media (max-width: 575.98px)" in layout
    assert "@media (min-width: 992px)" in layout


def test_every_table_is_wrapped_in_table_responsive():
    for template in TEMPLATES.rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        assert text.count("<table") == text.count('<div class="table-responsive">'), template.name


def test_bootstrap_and_fonts_are_served_locally(client):
    for path in (
        "vendor/bootstrap/bootstrap.min.css",
        "vendor/bootstrap/bootstrap.bundle.min.js",
        "fonts/archivo-variable.woff2",
        "fonts/barlow-condensed-700.woff2",
    ):
        assert client.get(f"/static/{path}").status_code == 200, path
    # the fonts are SIL Open Font License: the licence travels with them
    assert (STATIC / "fonts" / "OFL-archivo.txt").is_file()
    assert (STATIC / "fonts" / "OFL-barlow-condensed.txt").is_file()


# --- N4.04: animation ---


def test_hero_text_animation_ends_fully_visible():
    """Regression: the text flickered when the animation depended on Bootstrap's "active" class."""
    animations = css("animations.css")
    keyframes = re.search(r"@keyframes hero-in\s*\{(.*?)\n\}", animations, re.S).group(1)
    rule = re.search(r"([^{}]+)\{\s*animation: hero-in[^;]*;", animations)

    assert "opacity: 1" in keyframes.split("to {")[1]  # the last frame is fully visible
    assert re.search(r"animation: hero-in [^;]*\bboth\b", animations)  # and it stays that way
    assert ".hero-caption" in rule.group(1) and ".active" not in rule.group(1)


def test_text_is_never_hidden_outside_the_animation():
    """If animations are off (reduced motion), the normal state must already be visible."""
    for name in CSS_FILES:
        without_keyframes = re.sub(r"@keyframes[^{]*\{.*?\n\}", "", css(name), flags=re.S)
        assert "opacity: 0" not in without_keyframes, name


def test_animations_stop_for_reduced_motion():
    reduced = css("animations.css").split("@media (prefers-reduced-motion: reduce)")[1]

    assert "animation: none !important" in reduced
    assert "transition: none !important" in reduced


# --- navigation and the shop look ---


def test_anonymous_visitor_sees_login_and_register(client):
    html = page(client)

    assert 'href="/login">Login</a>' in html
    assert 'href="/register">Register</a>' in html
    assert "Logout" not in html


def test_customer_sees_account_links_and_a_csrf_logout_form(client):
    html = page(register_and_login(client))

    assert 'href="/orders">My orders</a>' in html
    assert 'href="/documents">Documents</a>' in html
    assert 'href="/admin/"' not in html
    form = re.search(r'<form method="post" action="/logout">.*?</form>', html, re.S).group(0)
    assert 'name="csrf_token"' in form


def test_cart_count_is_a_light_badge(app, client):
    with app.app_context():
        seed_products()
    assert "cart-count" not in page(client)

    client.post("/cart/add/1", data={"quantity": 2})

    assert '<span class="badge cart-count text-bg-light">2</span>' in page(client)


def test_error_pages_use_the_white_panel(client):
    response = client.get("/no-such-page")

    assert response.status_code == 404
    assert '<section class="panel">' in response.get_data(as_text=True)


# --- N4.03: the image carousel (the dark hero of the home page) ---


def hero(client):
    return page(client).split('id="heroCarousel"')[1].split("</section>")[0]


def test_the_carousel_shows_every_vehicle_and_only_vehicles(app, client):
    with app.app_context():
        seed_products()
    html = hero(client)

    assert len(re.findall(r"carousel-item(?![-\w])", html)) == 3  # the 3 sample vehicles
    assert len(re.findall(r"data-bs-slide-to=", html)) == 3
    assert "KTM 250 EXC-F" in html and "Enduro Helmet Pro" not in html


def test_exactly_one_slide_starts_active(app, client):
    with app.app_context():
        seed_products()

    assert hero(client).count("carousel-item active") == 1


def test_each_slide_has_alt_text_price_specs_and_a_link(app, client):
    with app.app_context():
        seed_products()
        ktm = VehicleProduct.query.filter_by(slug="ktm-250-exc-f").one()
        summary = ktm.get_technical_summary()
    html = hero(client)

    assert 'alt="KTM 250 EXC-F"' in html
    assert '<p class="hero-price">10,999.00 EUR</p>' in html
    assert f'<p class="product-specs">{summary}</p>' in html
    assert "/product/ktm-250-exc-f" in html


def test_the_carousel_controls_are_labelled(app, client):
    with app.app_context():
        seed_products()
    html = page(client)

    assert ">Previous</span>" in html and ">Next</span>" in html
    assert 'aria-label="Featured vehicles"' in html


def test_no_carousel_without_vehicles(client):
    assert "heroCarousel" not in page(client)


def test_the_active_category_is_underlined_and_marked(client):
    html = page(client, "/category/gear")

    assert html.count('aria-current="page"') == 1
    assert re.search(r'class="nav-link active"\s+href="/category/gear"', html)
