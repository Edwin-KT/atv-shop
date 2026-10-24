from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentItem:
    name: str
    unit_amount_cents: int
    quantity: int


@dataclass(frozen=True)
class CheckoutSession:
    session_id: str
    url: str


@dataclass(frozen=True)
class PaymentResult:
    paid: bool
    order_reference: str | None


class PaymentGateway(ABC):
    """Contract every payment provider must follow.

    The rest of the app depends only on this interface, so Stripe can be
    replaced (or faked in tests) without touching the order logic."""

    @abstractmethod
    def create_checkout_session(
        self,
        order_reference: str,
        items: list[PaymentItem],
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        """Start a hosted payment page. Raises PaymentError on failure."""

    @abstractmethod
    def get_payment_result(self, session_id: str) -> PaymentResult:
        """Ask the provider whether the session was paid. Raises PaymentError."""

    @abstractmethod
    def cancel_checkout_session(self, session_id: str) -> None:
        """Make an unpaid session unusable. Raises PaymentError.""" 