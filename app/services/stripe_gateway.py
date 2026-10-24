import stripe

from app.exceptions import PaymentError
from app.services.payment_interface import (
    CheckoutSession,
    PaymentGateway,
    PaymentItem,
    PaymentResult,
)


class StripeGateway(PaymentGateway):
    """PaymentGateway implemented with Stripe Checkout (hosted payment page)."""

    def __init__(self, secret_key: str | None, currency: str = "eur"):
        self._secret_key = secret_key
        self._currency = currency

    def _key(self) -> str:
        if not self._secret_key:
            raise PaymentError("Stripe is not configured (missing STRIPE_SECRET_KEY).")
        return self._secret_key

    def create_checkout_session(self, order_reference, items, success_url, cancel_url):
        key = self._key()
        try:
            session = stripe.checkout.Session.create(
                api_key=key,
                mode="payment",
                client_reference_id=order_reference,
                success_url=success_url,
                cancel_url=cancel_url,
                line_items=[
                    {
                        "quantity": item.quantity,
                        "price_data": {
                            "currency": self._currency,
                            "unit_amount": item.unit_amount_cents,  # already in cents
                            "product_data": {"name": item.name},
                        },
                    }
                    for item in items
                ],
            )
        except stripe.StripeError as exc:
            raise PaymentError("Stripe could not start the checkout.") from exc
        return CheckoutSession(session_id=session.id, url=session.url)

    def get_payment_result(self, session_id):
        key = self._key()
        try:
            session = stripe.checkout.Session.retrieve(session_id, api_key=key)
        except stripe.StripeError as exc:
            raise PaymentError("Stripe could not confirm the payment status.") from exc
        return PaymentResult(
            paid=session.payment_status == "paid",
            order_reference=session.client_reference_id,
        )

    def cancel_checkout_session(self, session_id):
        key = self._key()
        try:
            stripe.checkout.Session.expire(session_id, api_key=key)
        except stripe.StripeError as exc:
            raise PaymentError("Stripe could not cancel the checkout session.") from exc