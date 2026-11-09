from flask import Flask, render_template
from werkzeug.exceptions import SecurityError
from werkzeug.middleware.proxy_fix import ProxyFix

from app.activity_log import setup_activity_log
from app.config import Config, check_required_settings
from app.extensions import csrf, db, limiter, login_manager
from app.security import add_security_headers


def create_app(test_config=None):
    """Application factory: builds and configures one Flask app."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    check_required_settings(app)

    # On Render the app runs behind a proxy that talks HTTPS to the browser and
    # plain HTTP to us. ProxyFix trusts that ONE proxy's X-Forwarded-Proto and
    # X-Forwarded-For headers, so request.is_secure (HSTS), url_for(_external=True)
    # (Stripe's return URLs) and request.remote_addr (log, rate limit) are correct.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    setup_activity_log(app)
    app.after_request(add_security_headers)

    db.init_app(app)
    csrf.init_app(app)  # every POST form must send a valid csrf_token
    login_manager.init_app(app)
    limiter.init_app(app)  # at most 100 requests per minute per IP

    from app.services.payment import StripeGateway

    app.extensions["payment_gateway"] = app.config.get("PAYMENT_GATEWAY") or StripeGateway(
        app.config.get("STRIPE_SECRET_KEY")
    )

    from app import models  # noqa: F401  (models must be imported before create_all)
    from app.cli import register_commands
    from app.routes import admin, auth, cart, checkout, documents, main
    from app import validators
    from app.activity_log import ADMIN_LOG_LINES
    from app.services.cart import cart_item_count
    from app.services.catalog import CATEGORIES, MAX_QUERY_LENGTH

    register_commands(app)
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(cart.bp)
    app.register_blueprint(documents.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(checkout.bp)

    @app.context_processor
    def inject_cart_count():
        """Makes `cart_item_count` available in every template (navbar badge)."""
        return {"cart_item_count": cart_item_count()}

    @app.context_processor
    def inject_captcha():
        return {
            "captcha_enabled": app.config["CAPTCHA_ENABLED"],
            "captcha_site_key": app.config["RECAPTCHA_SITE_KEY"],
        }

    @app.context_processor
    def inject_navigation():
        return {"nav_categories": [(key, info["label"]) for key, info in CATEGORIES.items()]}

    @app.context_processor
    def inject_limits():
        """The only place templates get the shop's limits from (maxlength, options...),
        so a limit is written once, in Python, and the HTML always matches the server."""
        return {
            "max_query_length": MAX_QUERY_LENGTH,
            "vehicle_types": validators.VEHICLE_TYPES,
            "max_name_length": validators.MAX_NAME_LENGTH,
            "max_description_length": validators.MAX_DESCRIPTION_LENGTH,
            "max_gear_size_length": validators.MAX_GEAR_SIZE_LENGTH,
            "admin_log_lines": ADMIN_LOG_LINES,
        }

    @app.template_filter("eur")
    def eur(cents):
        """Prices are stored in whole cents: {{ 1299900|eur }} -> '12,999.00 EUR'."""
        return f"{cents / 100:,.2f} EUR"

    # One error page for every error we expect: (title, message) per status code.
    limit_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    error_pages = {
        # 400 is also what a missing or wrong CSRF token gives, so the text stays general.
        400: ("Bad request", "The request could not be processed. Please go back and try again."),
        403: ("Access denied", "You do not have permission to open this page."),
        404: ("Page not found", "The page you are looking for does not exist."),
        413: ("File too large", f"Uploads are limited to {limit_mb} MB."),
        429: ("Too many requests", "You are sending requests too fast. Please wait a minute and try again."),
        # Any unexpected exception (a bug, the database down): no details for the visitor;
        # Flask writes the traceback to the server log (Render: "Logs").
        500: ("Something went wrong", "An unexpected error happened on our side. Please try again in a moment."),
    }

    def show_error_page(error):
        if error.code == 500:
            # After a failed commit the session is unusable until rolled back, and
            # this page needs it too (the navbar loads the logged-in user).
            db.session.rollback()
        title, message = error_pages[error.code]
        return render_template("error.html", title=title, message=message), error.code

    for code in error_pages:
        app.register_error_handler(code, show_error_page)

    def refuse_untrusted_host(error):
        # A Host outside TRUSTED_HOSTS: no URL can be built for it, so the
        # normal page (full of url_for links) cannot be shown. Plain text instead.
        return "Bad request: unknown host.", 400, {"Content-Type": "text/plain; charset=utf-8"}

    app.register_error_handler(SecurityError, refuse_untrusted_host)

    with app.app_context():
        db.create_all()  # no migrations: creates the tables that do not exist yet

    return app
