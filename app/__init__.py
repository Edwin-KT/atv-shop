from flask import Flask


def create_app(test_config=None):
    """Application factory: lets us create separate app instances
    (one for production, one for each test)."""
    app = Flask(__name__)
    app.config.from_mapping(SECRET_KEY="dev-only-change-me")

    if test_config:
        app.config.update(test_config)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app