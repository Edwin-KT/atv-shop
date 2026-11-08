"""UNIT tests for app/services/payment.py: the PaymentGateway interface and the Stripe
implementation, called directly (Stripe's own functions are replaced, no network).

Rubric: N3.02 an interface (an abstract class with abstract methods) that is
defined and used; N8.02 online payments with Stripe; N4.02 the PaymentError
exception; N6.01 unit tests."""

from types import SimpleNamespace

import pytest
import stripe
from fake_gateway import FakeGateway

from app.exceptions import PaymentError
from app.services.payment import PaymentGateway, StripeGateway

# Just what create_checkout reads from an order: its id and its items.
ORDER = SimpleNamespace(
    id=42,
    items=[SimpleNamespace(product=SimpleNamespace(name="Enduro Helmet Pro"), unit_price_cents=18_900, quantity=2)],
)


def test_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        PaymentGateway()


def test_a_gateway_missing_a_method_cannot_be_instantiated():
    class HalfGateway(PaymentGateway):
        def create_checkout(self, order, success_url, cancel_url):
            return "cs_1", "https://pay.example.test"

    with pytest.raises(TypeError):
        HalfGateway()


def test_implementations_follow_the_interface():
    assert issubclass(StripeGateway, PaymentGateway)
    assert issubclass(FakeGateway, PaymentGateway)


def test_stripe_without_key_raises_payment_error():
    with pytest.raises(PaymentError):
        StripeGateway(None).create_checkout(ORDER, "http://s", "http://c")


def test_stripe_session_is_created_with_amounts_in_cents(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.com/pay/cs_test_1")

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)

    session_id, url = StripeGateway("sk_test_x").create_checkout(ORDER, "http://success", "http://cancel")

    assert (session_id, url) == ("cs_test_1", "https://checkout.stripe.com/pay/cs_test_1")
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
        StripeGateway("sk_test_x").create_checkout(ORDER, "http://s", "http://c")


@pytest.mark.parametrize("status, expected", [("paid", True), ("unpaid", False)])
def test_stripe_is_paid_reads_the_payment_status(monkeypatch, status, expected):
    monkeypatch.setattr(
        stripe.checkout.Session,
        "retrieve",
        lambda session_id, **kwargs: SimpleNamespace(payment_status=status),
    )

    assert StripeGateway("sk_test_x").is_paid("cs_test_1") is expected
