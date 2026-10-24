class FakeCaptcha:
    """Accepts only the token 'valid-token'. No network."""

    def __init__(self):
        self.calls = []

    def verify(self, token, remote_ip=None):
        self.calls.append((token, remote_ip))
        return token == "valid-token"