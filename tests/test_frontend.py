import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
TEMPLATES = ROOT / "app" / "templates"
CSS_FILES = [
    STATIC / "css" / name
    for name in ("base.css", "layout.css", "components.css", "pages.css", "animations.css")
]


def all_css() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in CSS_FILES)


def css_properties(path: Path) -> set[str]:
    """Distinct standard CSS properties used in a stylesheet (custom --vars excluded)."""
    css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
    names = set()
    for block in re.findall(r"\{([^{}]*)\}", css):
        for declaration in block.split(";"):
            if ":" in declaration:
                name = declaration.split(":")[0].strip()
                if name and not name.startswith("--"):
                    names.add(name)
    return names





def test_bootstrap_is_served_locally(client):
    html = client.get("/").get_data(as_text=True)

    assert "cdn.jsdelivr.net" not in html
    assert client.get("/static/vendor/bootstrap/bootstrap.min.css").status_code == 200
    assert client.get("/static/vendor/bootstrap/bootstrap.bundle.min.js").status_code == 200


def test_templates_have_no_inline_styles_or_handlers():
    """Prepares the strict Content-Security-Policy planned for step H."""
    for template in TEMPLATES.rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        assert 'style="' not in text, f"inline style in {template.name}"
        assert not re.search(r"\son[a-z]+=", text), f"inline event handler in {template.name}"


def test_catalog_uses_square_images(app, client):
    from app.seed import seed_products

    with app.app_context():
        seed_products()

    assert "ratio-1x1" in client.get("/").get_data(as_text=True)


def test_navbar_collapses_on_small_screens(client):
    html = client.get("/").get_data(as_text=True)

    assert "navbar-toggler" in html
    assert 'name="viewport"' in html


def test_animations_are_defined_in_css():
    css = (STATIC / "css" / "animations.css").read_text(encoding="utf-8")

    assert "@keyframes" in css
    assert "animation:" in css


def test_animations_respect_reduced_motion():
    css = (STATIC / "css" / "animations.css").read_text(encoding="utf-8")

    assert "prefers-reduced-motion: reduce" in css


def test_animation_stylesheet_and_script_are_linked(client):
    html = client.get("/").get_data(as_text=True)

    assert "css/animations.css" in html
    assert "js/reduced-motion.js" in html


def test_scroll_reveal_is_gone(app, client):
    from app.seed import seed_products

    with app.app_context():
        seed_products()

    html = client.get("/").get_data(as_text=True)

    assert "reveal" not in html


def test_hero_light_sweep_is_hidden_unless_animated():
    css = (STATIC / "css" / "animations.css").read_text(encoding="utf-8")

    assert "@keyframes sweep" in css
    assert ".carousel-item.active .hero-photo::after" in css
    # the light must be invisible by default, so it can never stay stuck on the photo
    base_rule = css.split(".hero-photo::after {")[1].split("}")[0]
    assert "opacity: 0" in base_rule


def test_title_bar_and_hover_effects_exist():
    css = (STATIC / "css" / "animations.css").read_text(encoding="utf-8")

    assert "@keyframes grow-bar" in css
    assert "scaleX(1)" in css

def test_every_page_has_the_viewport_meta(client):
    for url in ("/", "/login", "/register", "/cart"):
        assert 'name="viewport"' in client.get(url).get_data(as_text=True)


def test_catalog_grid_adapts_to_screen_size(app, client):
    from app.seed import seed_products

    with app.app_context():
        seed_products()

    html = client.get("/").get_data(as_text=True)

    assert "row-cols-1" in html      # phone
    assert "row-cols-sm-2" in html   # tablet
    assert "row-cols-lg-3" in html   # desktop


def test_tables_scroll_instead_of_overflowing():
    for name in ("cart.html", "documents.html", "checkout/review.html"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        if "<table" in text:
            assert "table-responsive" in text, f"{name} has a table without table-responsive"

def test_project_has_several_css_files_with_enough_distinct_properties():
    assert len(CSS_FILES) >= 2
    assert all(path.is_file() for path in CSS_FILES)
    all_properties = set().union(*(css_properties(path) for path in CSS_FILES))
    assert len(all_properties) >= 15  # the requirement is 10


def test_each_css_file_is_linked_from_the_pages(client):
    html = client.get("/").get_data(as_text=True)

    for path in CSS_FILES:
        assert f"css/{path.name}" in html


def test_css_files_are_linked_from_general_to_specific(client):
    html = client.get("/").get_data(as_text=True)

    order = [html.index(f"css/{name}") for name in
             ("base.css", "layout.css", "components.css", "pages.css", "animations.css")]
    assert order == sorted(order)


def test_css_has_media_queries_for_phone_and_tablet():
    css = all_css()

    assert "max-width: 575.98px" in css   # phone
    assert "min-width: 768px" in css      # tablet
    assert "max-width: 991.98px" in css   # collapsed menu


def test_css_does_not_break_words_everywhere():
    css = all_css()

    assert "main {\n  overflow-wrap: anywhere" not in css
    assert "white-space: nowrap" in css  # prices and quantities stay on one line


def test_variables_are_defined_once_in_base_css():
    for path in CSS_FILES:
        text = path.read_text(encoding="utf-8")
        if path.name != "base.css":
            assert ":root" not in text, f"{path.name} must not redefine design tokens"