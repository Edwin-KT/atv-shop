from app.exceptions import PaymentError
from app.services.payment import PaymentGateway


class FakeGateway(PaymentGateway):
    """In-memory PaymentGateway for the tests: no network, fully controllable."""

    def __init__(self):
        self.sessions = {}  # session_id -> what the shop sent
        self.paid = set()
        self.expired = set()
        self.fail_next_create = False
        self.fail_next_expire = False
        self._counter = 0

    def create_checkout(self, order, success_url, cancel_url):
        if self.fail_next_create:
            self.fail_next_create = False
            raise PaymentError("fake failure")
        self._counter += 1
        session_id = f"cs_fake_{self._counter}"
        self.sessions[session_id] = {
            "order_id": order.id,
            "items": [(i.product.name, i.unit_price_cents, i.quantity) for i in order.items],
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        return session_id, f"https://pay.example.test/{session_id}"

    def is_paid(self, session_id):
        if session_id not in self.sessions:
            raise PaymentError("unknown session")
        return session_id in self.paid

    def expire(self, session_id):
        if self.fail_next_expire:
            self.fail_next_expire = False
            raise PaymentError("fake failure")
        self.expired.add(session_id)

    def mark_paid(self, session_id):
        """Test helper: the customer paid on the provider's page."""
        self.paid.add(session_id)
