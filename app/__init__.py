from pathlib import Path

from flask import Flask, render_template, url_for
from sqlalchemy import text

from app.access_log import configure_access_log
from app.config import Config
from app.extensions import csrf, db, limiter, login_manager
from app.logging_config import configure_logging
from app.security_headers import register_security_headers


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    configure_logging(app)
    configure_access_log(app)
    register_security_headers(app)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    from app.services.stripe_gateway import StripeGateway

    app.extensions["payment_gateway"] = app.config.get("PAYMENT_GATEWAY") or StripeGateway(
        app.config.get("STRIPE_SECRET_KEY")
    )

    from app.services.captcha import RecaptchaVerifier

    app.extensions["captcha_verifier"] = app.config.get("CAPTCHA_VERIFIER") or RecaptchaVerifier(
        app.config.get("RECAPTCHA_SECRET_KEY")
    )

    from app import models  # noqa: F401  (models must be imported before create_all)
    from app.cli import register_commands
    from app.routes import admin, auth, cart, checkout, documents, main, seo
    from app.services.cart import cart_item_count

    register_commands(app)
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(cart.bp)
    app.register_blueprint(documents.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(checkout.bp)
    app.register_blueprint(seo.bp)

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
    def inject_seo():
        return {
            "site_url": app.config["SITE_URL"],
            "site_name": app.config["SITE_NAME"],
        }

    @app.context_processor
    def inject_navigation():
        from app.catalog import CATEGORIES

        return {"nav_categories": [(key, info["label"]) for key, info in CATEGORIES.items()]}
    
    def product_image_path(product):
        """Path of the product photo, or of the placeholder if the file does not exist."""
        if product.image_filename:
            photo = Path(app.static_folder) / "img" / "products" / product.image_filename
            if photo.is_file():
                return url_for("static", filename=f"img/products/{product.image_filename}")
        return url_for("static", filename="img/placeholder.svg")

    app.jinja_env.globals["product_image_url"] = product_image_path
    app.extensions["product_image_path"] = product_image_path

    @app.errorhandler(403)
    def forbidden(error):
        return (
            render_template(
                "error.html",
                title="Access denied",
                message="You do not have permission to open this page.",
            ),
            403,
        )

    @app.errorhandler(413)
    def file_too_large(error):
        limit_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return (
            render_template(
                "error.html",
                title="File too large",
                message=f"Uploads are limited to {limit_mb} MB.",
            ),
            413,
        )

    @app.errorhandler(429)
    def too_many_requests(error):
        from app.services.audit import record_event

        record_event("rate_limited", details=str(error.description)[:200])
        page = render_template(
            "error.html",
            title="Too many requests",
            message="You are sending requests too fast. Please wait a minute and try again.",
        )
        return page, 429, {"Retry-After": "60"}

    with app.app_context():
        db.create_all()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/health/db")
    def health_db():
        db.session.execute(text("SELECT 1"))
        return {"database": "ok"}

    return app