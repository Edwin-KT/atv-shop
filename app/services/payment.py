"""Online payments: the PaymentGateway interface and its Stripe implementation."""

from abc import ABC, abstractmethod

import stripe

from app.exceptions import PaymentError


class PaymentGateway(ABC):
    """Interface: what the shop needs from any payment provider.

    The order code only calls these three methods, so Stripe can be swapped for
    another provider, or for a fake one in the tests, without changing it.
    ABC + @abstractmethod: this class cannot be instantiated, and a subclass that
    forgets a method cannot be instantiated either."""

    @abstractmethod
    def create_checkout(self, order, success_url: str, cancel_url: str) -> tuple[str, str]:
        """Open a hosted payment page for the order.
        Returns (session_id, payment_page_url). Raises PaymentError."""

    @abstractmethod
    def is_paid(self, session_id: str) -> bool:
        """Ask the provider whether this payment page was paid. Raises PaymentError."""

    @abstractmethod
    def expire(self, session_id: str) -> None:
        """Close an unpaid payment page, so a cancelled order can no longer be paid.
        A page that already expired on its own is not an error. Raises PaymentError
        when the page cannot be closed (provider unreachable, or already paid)."""


class StripeGateway(PaymentGateway):
    """PaymentGateway implemented with Stripe Checkout (Stripe hosts the card form)."""

    def __init__(self, secret_key: str | None):
        self._secret_key = secret_key

    def _key(self) -> str:
        if not self._secret_key:
            raise PaymentError("Stripe is not configured (missing STRIPE_SECRET_KEY).")
        return self._secret_key

    def create_checkout(self, order, success_url, cancel_url):
        line_items = [
            {
                "quantity": item.quantity,
                "price_data": {
                    "currency": "eur",
                    "unit_amount": item.unit_price_cents,  # Stripe also counts in cents
                    "product_data": {"name": item.product.name},
                },
            }
            for item in order.items
        ]
        try:
            session = stripe.checkout.Session.create(
                api_key=self._key(),
                mode="payment",
                client_reference_id=str(order.id),  # shows our order number in Stripe
                line_items=line_items,
                success_url=success_url,
                cancel_url=cancel_url,
            )
        except stripe.StripeError as exc:
            raise PaymentError("Stripe could not start the checkout.") from exc
        return session.id, session.url

    def is_paid(self, session_id):
        try:
            session = stripe.checkout.Session.retrieve(session_id, api_key=self._key())
        except stripe.StripeError as exc:
            raise PaymentError("Stripe could not confirm the payment status.") from exc
        return session.payment_status == "paid"

    def expire(self, session_id):
        # Stripe can only expire an "open" session, and closes them by itself after
        # 24 hours; asking first keeps those old orders cancellable.
        try:
            session = stripe.checkout.Session.retrieve(session_id, api_key=self._key())
            if session.status == "open":
                stripe.checkout.Session.expire(session_id, api_key=self._key())
        except stripe.StripeError as exc:
            raise PaymentError("Stripe could not cancel the checkout session.") from exc
        if session.status == "complete":  # the customer has just paid
            raise PaymentError("The checkout session is already completed.")
