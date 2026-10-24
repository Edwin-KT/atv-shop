from app.exceptions import PaymentError
from app.services.payment_interface import CheckoutSession, PaymentGateway, PaymentResult


class FakeGateway(PaymentGateway):
    """In-memory gateway for tests: no network, fully controllable."""

    def __init__(self):
        self.sessions = {}
        self.paid = set()
        self.cancelled = set()
        self.fail_next_create = False
        self._counter = 0

    def create_checkout_session(self, order_reference, items, success_url, cancel_url):
        if self.fail_next_create:
            self.fail_next_create = False
            raise PaymentError("fake failure")
        self._counter += 1
        session_id = f"cs_fake_{self._counter}"
        self.sessions[session_id] = {
            "order_reference": order_reference,
            "items": items,
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        return CheckoutSession(session_id, f"https://pay.example.test/{session_id}")

    def get_payment_result(self, session_id):
        if session_id not in self.sessions:
            raise PaymentError("unknown session")
        return PaymentResult(
            paid=session_id in self.paid,
            order_reference=self.sessions[session_id]["order_reference"],
        )

    def cancel_checkout_session(self, session_id):
        self.cancelled.add(session_id)

    def mark_paid(self, session_id):
        self.paid.add(session_id)