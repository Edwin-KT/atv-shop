"""Our own exception types. Each one is raised by a service and caught in a route."""


class OutOfStockError(Exception):
    """Not enough stock left for a product at checkout."""

    def __init__(self, product_name: str):
        super().__init__(f"Not enough stock for {product_name}.")
        self.product_name = product_name


class PaymentError(Exception):
    """The payment provider failed or returned something unexpected."""
