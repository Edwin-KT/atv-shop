class ShopError(Exception):
    """Base class for errors raised by the shop's business logic."""


class EmptyCartError(ShopError):
    pass


class OutOfStockError(ShopError):
    def __init__(self, product_name: str):
        super().__init__(f"Not enough stock for {product_name}.")
        self.product_name = product_name


class PaymentError(ShopError):
    """The payment provider failed or returned something unexpected."""