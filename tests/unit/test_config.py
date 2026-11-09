"""UNIT tests: the settings needed to run in production (Render + Neon).

Rubric: N10.04 security (no unsafe default secrets; the app refuses to start without them);
deploy on Render with a Neon database."""

import pytest
from flask import Flask

from app.config import DEV_SECRET_KEY, check_required_settings, with_psycopg_driver

NEON_URL = "postgresql://user:pw@ep-example.eu-central-1.aws.neon.tech/shop?sslmode=require"


def bare_app(**settings):
    """A plain Flask app with only the settings that check_required_settings reads."""
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="a-real-secret",
        CAPTCHA_ENABLED=True,
        RECAPTCHA_SITE_KEY="site",
        RECAPTCHA_SECRET_KEY="secret",
    )
    app.config.update(settings)
    return app


# --- DATABASE_URL from Neon ---


def test_a_neon_url_gets_the_psycopg_driver():
    assert with_psycopg_driver(NEON_URL) == (
        "postgresql+psycopg://user:pw@ep-example.eu-central-1.aws.neon.tech/shop?sslmode=require"
    )


def test_a_url_that_names_the_driver_stays_the_same():
    url = "postgresql+psycopg://enduro_admin:pw@localhost:5433/atv_shop"
    assert with_psycopg_driver(url) == url
    assert with_psycopg_driver(None) is None


# --- required secrets ---


def test_production_with_every_setting_starts():
    check_required_settings(bare_app())  # does not raise


def test_production_refuses_to_start_without_a_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        check_required_settings(bare_app(SECRET_KEY=None))


def test_production_refuses_to_start_without_the_recaptcha_keys():
    with pytest.raises(RuntimeError, match="RECAPTCHA_SITE_KEY, RECAPTCHA_SECRET_KEY"):
        check_required_settings(bare_app(RECAPTCHA_SITE_KEY=None, RECAPTCHA_SECRET_KEY=""))


def test_the_recaptcha_keys_are_not_needed_when_the_captcha_is_off():
    check_required_settings(bare_app(CAPTCHA_ENABLED=False, RECAPTCHA_SITE_KEY=None, RECAPTCHA_SECRET_KEY=None))


@pytest.mark.parametrize("mode", ["TESTING", "DEBUG"])
def test_tests_and_debug_mode_start_with_the_development_key(mode):
    app = bare_app(SECRET_KEY=None, RECAPTCHA_SITE_KEY=None, **{mode: True})

    check_required_settings(app)

    assert app.config["SECRET_KEY"] == DEV_SECRET_KEY
