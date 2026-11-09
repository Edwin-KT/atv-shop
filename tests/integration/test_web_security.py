"""INTEGRATION tests: protections against common web attacks, through the app (plus
checks of the templates and of the .htaccess files).

Rubric: N9.01 CSRF; N9.02 XSS (escaping + strict CSP); N9.03 SQL injection;
N10.04 security headers (grade A) incl. HSTS behind the proxy (ProxyFix);
N10.05 .htaccess rules."""

import re
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models import Product
from helpers import PASSWORD, page, seed

ROOT = Path(__file__).resolve().parents[2]  # the project folder
TEMPLATES = ROOT / "app" / "templates"


def app_with_csrf_on():
    # The normal test app switches CSRF off so the other tests can post forms easily.
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": True})


# --- N9.01 CSRF ---


def test_a_post_without_a_csrf_token_is_refused():
    response = app_with_csrf_on().test_client().post(
        "/register", data={"email": "ana@gmail.com", "phone": "0712345678", "password": PASSWORD}
    )

    assert response.status_code == 400
    assert "Bad request" in response.get_data(as_text=True)  # our own error page


def test_the_forms_contain_a_csrf_token():
    client = app_with_csrf_on().test_client()

    for url in ("/register", "/login"):
        assert 'name="csrf_token"' in page(client, url), url


# --- N9.02 XSS ---


def test_script_typed_in_the_search_is_shown_as_text(client):
    html = page(client, "/search?q=<script>alert(1)</script>")

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_script_in_a_product_name_is_escaped_on_every_page(app, client):
    seed(app)
    with app.app_context():
        Product.query.filter_by(slug="enduro-helmet-pro").one().name = '<script>alert("x")</script>'
        db.session.commit()

    for url in ("/", "/product/enduro-helmet-pro"):
        html = page(client, url)
        assert '<script>alert("x")</script>' not in html
        assert "&lt;script&gt;" in html


def test_html_in_an_email_never_reaches_the_page_raw(client):
    email = "<img src=x onerror=alert(1)>@gmail.com"
    client.post("/register", data={"email": email, "phone": "0712345678", "password": PASSWORD})

    html = client.post("/login", data={"email": email, "password": PASSWORD}).get_data(as_text=True)

    assert "<img src=x" not in html  # refused or escaped, never raw


def test_templates_never_switch_escaping_off():
    for template in TEMPLATES.rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        assert "|safe" not in text and "| safe" not in text, template.name
        assert "{% autoescape false" not in text, template.name


def test_there_are_no_inline_scripts_or_event_handlers():
    """Every <script> loads a file (src=...), so the strict CSP needs no exception."""
    for template in TEMPLATES.rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", text), template.name
        assert not re.search(r"\son[a-z]+=", text), template.name


# --- N9.03 SQL injection ---


def test_sql_typed_in_the_search_finds_nothing(app, client):
    """The ORM sends the text as a bound parameter, so it is only searched for, never run."""
    seed(app)

    response = client.get("/search?q=' OR 1=1 --")

    assert response.status_code == 200
    assert "No products match" in response.get_data(as_text=True)


# --- N10.04 security headers ---


def test_all_security_headers_are_present(client):
    headers = client.get("/").headers

    for name in ("Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options",
                 "Referrer-Policy", "Permissions-Policy"):
        assert name in headers, f"missing {name}"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"


def test_the_csp_is_strict(client):
    csp = client.get("/").headers["Content-Security-Policy"]

    assert "default-src 'self'" in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert "frame-ancestors 'none'" in csp
    assert "https://checkout.stripe.com" in csp  # the redirect to Stripe must stay allowed


def test_headers_are_also_on_error_pages_and_static_files(client):
    assert "Content-Security-Policy" in client.get("/does-not-exist").headers
    assert "X-Content-Type-Options" in client.get("/static/css/layout.css").headers


def test_hsts_only_over_https_including_behind_the_proxy(client):
    assert "Strict-Transport-Security" not in client.get("/").headers

    assert "max-age=31536000" in client.get("/", base_url="https://localhost").headers["Strict-Transport-Security"]
    # On Render the proxy says "the visitor used HTTPS"; ProxyFix reads that header.
    behind_proxy = client.get("/", headers={"X-Forwarded-Proto": "https"})
    assert "max-age=31536000" in behind_proxy.headers["Strict-Transport-Security"]


def test_only_the_trusted_host_is_accepted(app):
    """Absolute URLs (sitemap, Stripe return URLs) come from the Host header,
    so in production a request for any other host is refused."""
    app.config["TRUSTED_HOSTS"] = ["shop.example"]
    client = app.test_client()

    assert client.get("/", base_url="http://shop.example").status_code == 200
    refused = client.get("/", base_url="http://evil.example")
    assert refused.status_code == 400
    assert refused.get_data(as_text=True) == "Bad request: unknown host."
    assert "Content-Security-Policy" in refused.headers  # security headers stay on


def test_the_session_cookie_can_be_https_only(app):
    app.config["SESSION_COOKIE_SECURE"] = True  # SESSION_COOKIE_SECURE=true on Render
    product_id = seed(app)["enduro-helmet-pro"]

    response = app.test_client().post(f"/cart/add/{product_id}")  # puts the cart in the session

    assert "; Secure" in response.headers["Set-Cookie"]


def test_only_the_last_proxy_hop_gives_the_visitor_ip(client, log_text):
    """A visitor can send a fake X-Forwarded-For; the proxy adds the real IP at the end,
    and x_for=1 only trusts that last value (used by the log and the rate limit)."""
    client.get("/", headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.7"})

    assert "ip=203.0.113.7 " in log_text()
    assert "6.6.6.6" not in log_text()


# --- N10.05 .htaccess ---


def test_the_uploads_folder_denies_everything():
    assert "Require all denied" in (ROOT / "private_uploads" / ".htaccess").read_text(encoding="utf-8")


def test_the_root_htaccess_blocks_secrets_code_and_listings_but_not_robots():
    rules = (ROOT / ".htaccess").read_text(encoding="utf-8")
    assert "private_uploads" in rules and "Options -Indexes" in rules
    # The FilesMatch pattern uses only syntax that Apache (PCRE) and Python share.
    pattern = re.compile(re.search(r'<FilesMatch "(.+?)">', rules).group(1))

    for name in [".env", "requirements.txt", "wsgi.py", "README.md", "app.log", "docker-compose.yml"]:
        assert pattern.search(name), f"{name} must be denied"
    for name in ["robots.txt", "sitemap.xml"]:
        assert not pattern.search(name), f"{name} must stay public"


def test_uploads_are_not_reachable_through_the_web_app(client):
    assert client.get("/private_uploads/anything.pdf").status_code == 404
    assert client.get("/static/../private_uploads/x.pdf").status_code == 404
