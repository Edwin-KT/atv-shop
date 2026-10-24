from types import SimpleNamespace

import pytest
import stripe
from fake_gateway import FakeGateway

from app.exceptions import PaymentError
from app.services.payment_interface import PaymentGateway, PaymentItem
from app.services.stripe_gateway import StripeGateway

ITEMS = [PaymentItem("Enduro Helmet Pro", 18_900, 2)]


def test_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        PaymentGateway()


def test_implementations_follow_the_interface():
    assert issubclass(StripeGateway, PaymentGateway)
    assert issubclass(FakeGateway, PaymentGateway)


def test_stripe_without_key_raises_payment_error():
    with pytest.raises(PaymentError):
        StripeGateway(None).create_checkout_session("1", ITEMS, "http://s", "http://c")


def test_stripe_session_is_created_with_amounts_in_cents(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.com/pay/cs_test_1")

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)

    session = StripeGateway("sk_test_x").create_checkout_session(
        "42", ITEMS, "http://success", "http://cancel"
    )

    assert session.session_id == "cs_test_1"
    assert captured["mode"] == "payment"
    assert captured["client_reference_id"] == "42"
    line = captured["line_items"][0]
    assert line["quantity"] == 2
    assert line["price_data"]["unit_amount"] == 18_900
    assert line["price_data"]["currency"] == "eur"


def test_stripe_errors_become_payment_errors(monkeypatch):
    def boom(**kwargs):
        raise stripe.StripeError("network down")

    monkeypatch.setattr(stripe.checkout.Session, "create", boom)

    with pytest.raises(PaymentError):
        StripeGateway("sk_test_x").create_checkout_session("1", ITEMS, "http://s", "http://c")


def test_stripe_payment_result(monkeypatch):
    monkeypatch.setattr(
        stripe.checkout.Session,
        "retrieve",
        lambda session_id, **kwargs: SimpleNamespace(
            payment_status="paid", client_reference_id="42"
        ),
    )

    result = StripeGateway("sk_test_x").get_payment_result("cs_test_1")

    assert result.paid is True
    assert result.order_reference == "42"