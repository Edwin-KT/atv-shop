from flask import Flask
from sqlalchemy import text

from app.config import Config
from app.extensions import db


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    from app import models  # noqa: F401  (models must be imported before create_all)
    from app.routes import auth, main

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)

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