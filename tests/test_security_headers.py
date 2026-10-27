import re
from pathlib import Path

from app.models import Product
from app.seed import seed_products

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
PASSWORD = "parola-sigura-123"


def test_all_security_headers_are_present(client):
    headers = client.get("/").headers

    for name in (
        "Content-Security-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
    ):
        assert name in headers, f"missing {name}"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"


def test_csp_is_strict(client):
    csp = client.get("/").headers["Content-Security-Policy"]

    assert "default-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "https://checkout.stripe.com" in csp  # the payment redirect must stay allowed


def test_headers_are_on_error_pages_and_static_files_too(client):
    assert "Content-Security-Policy" in client.get("/does-not-exist").headers
    assert "X-Content-Type-Options" in client.get("/static/css/layout.css").headers


def test_hsts_only_over_https(client):
    assert "Strict-Transport-Security" not in client.get("/").headers

    secure = client.get("/", base_url="https://localhost")
    assert "max-age=31536000" in secure.headers["Strict-Transport-Security"]


def test_html_pages_are_not_cached(client):
    assert client.get("/").headers["Cache-Control"] == "no-store"


# --- XSS ---

def test_templates_never_disable_escaping():
    for template in TEMPLATES.rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        assert "|safe" not in text and "| safe" not in text, template.name
        assert "{% autoescape false" not in text, template.name


def test_no_inline_scripts_or_handlers():
    for template in TEMPLATES.rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        for match in re.finditer(r'<script(?![^>]*\bsrc=)(?![^>]*application/ld\+json)[^>]*>', text):
            raise AssertionError(f"inline <script> in {template.name}: {match.group(0)}")
        assert not re.search(r"\son[a-z]+=", text), template.name


def test_script_in_product_name_is_escaped_on_every_page(app, client):
    with app.app_context():
        seed_products()
        product = Product.query.filter_by(slug="enduro-helmet-pro").one()
        product.name = '<script>alert("x")</script>'
        from app.extensions import db

        db.session.commit()

    for url in ("/", "/product/enduro-helmet-pro"):
        html = client.get(url).get_data(as_text=True)
        assert '<script>alert("x")</script>' not in html
        assert "&lt;script&gt;" in html


def test_script_in_email_is_escaped_in_the_navbar(client):
    email = "<img src=x onerror=alert(1)>@gmail.com"
    client.post("/register", data={"email": email, "phone": "0712345678", "password": PASSWORD})

    html = client.post("/login", data={"email": email, "password": PASSWORD}).get_data(as_text=True)
    assert "<img src=x" not in html  # rejected or escaped, never raw