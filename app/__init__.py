from flask import Flask
from sqlalchemy import text

from app.config import Config
from app.extensions import csrf, db, login_manager
from app.logging_config import configure_logging


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    configure_logging(app)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    from app import models  # noqa: F401  (models must be imported before create_all)
    from app.cli import register_commands
    from app.routes import auth, cart, main
    from app.services.cart import cart_item_count

    register_commands(app)
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(cart.bp)

    @app.context_processor
    def inject_cart_count():
        """Makes `cart_item_count` available in every template (navbar badge)."""
        return {"cart_item_count": cart_item_count()}

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