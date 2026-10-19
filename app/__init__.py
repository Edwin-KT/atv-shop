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

    with app.app_context():
        db.create_all()  # creates tables for every model that exists

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/health/db")
    def health_db():
        db.session.execute(text("SELECT 1"))
        return {"database": "ok"}

    return app