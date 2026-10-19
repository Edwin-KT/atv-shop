import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(app):
    """Send application logs to logs/app.log (rotated at ~1 MB, 3 old files kept)."""
    if app.config.get("TESTING"):
        return  # tests don't write files; pytest captures logs itself

    log_dir = Path(app.root_path).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)