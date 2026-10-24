import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
TEMPLATES = ROOT / "app" / "templates"
CSS_FILES = [STATIC / "css" / "layout.css", STATIC / "css" / "components.css"]


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


def test_project_has_two_css_files_with_enough_distinct_properties():
    assert all(path.is_file() for path in CSS_FILES)
    all_properties = set().union(*(css_properties(path) for path in CSS_FILES))
    assert len(all_properties) >= 15  # the requirement is 10


def test_each_css_file_is_linked_from_the_pages(client):
    html = client.get("/").get_data(as_text=True)

    assert "css/layout.css" in html
    assert "css/components.css" in html


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