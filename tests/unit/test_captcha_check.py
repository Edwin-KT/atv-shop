"""UNIT tests for ask_google() in app/services/captcha.py: the server-side CAPTCHA
check, called directly inside a fake request (Google's answer is faked, no network).

Rubric: N10.02 CAPTCHA, which "fails closed": any problem (no token, no secret key,
network error, strange answer) counts as "not a human"; N6.01 unit tests."""

import pytest
import requests

from app.services.captcha import VERIFY_URL, ask_google


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self._payload = payload if payload is not None else {}
        self._status = status

    def raise_for_status(self):
        if self._status >= 400:
            raise requests.HTTPError("bad status")

    def json(self):
        return self._payload


# --- asking Google (unit tests, network faked) ---


def ask(app, token):
    with app.test_request_context("/login", method="POST", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
        return ask_google(token)


def test_google_is_asked_with_the_secret_token_and_ip(app, monkeypatch):
    captured = {}

    def fake_post(url, data, timeout):
        captured.update(url=url, data=data, timeout=timeout)
        return FakeResponse({"success": True})

    monkeypatch.setattr(requests, "post", fake_post)

    assert ask(app, "token-1") is True
    assert captured["url"] == VERIFY_URL
    assert captured["data"]["response"] == "token-1"
    assert captured["data"]["secret"] == app.config["RECAPTCHA_SECRET_KEY"]
    assert captured["data"]["remoteip"] == "127.0.0.1"
    assert captured["timeout"] > 0


def test_token_refused_by_google_fails(app, monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"success": False}))

    assert ask(app, "token-1") is False


def test_fails_closed_on_network_error(app, monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests, "post", boom)

    assert ask(app, "token-1") is False


def test_fails_closed_on_a_bad_answer(app, monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse(status=500))
    assert ask(app, "token-1") is False

    class NotJson(FakeResponse):
        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(requests, "post", lambda *a, **k: NotJson())
    assert ask(app, "token-1") is False


@pytest.mark.parametrize("token", ["", None, "x" * 5000])
def test_unusable_tokens_are_not_sent_to_google(app, monkeypatch, token):
    def must_not_run(*args, **kwargs):
        raise AssertionError("network call made")

    monkeypatch.setattr(requests, "post", must_not_run)

    assert ask(app, token) is False


def test_without_a_secret_key_everything_fails(app, monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"success": True}))
    app.config["RECAPTCHA_SECRET_KEY"] = ""

    assert ask(app, "token-1") is False
