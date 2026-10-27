from flask import request

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-src https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/",
        "form-action 'self' https://checkout.stripe.com",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "object-src 'none'",
    ]
)

PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), payment=(), usb=()"
)

HSTS = "max-age=31536000; includeSubDomains"

PRIVATE_PREFIXES = (
    "/admin", "/cart", "/checkout", "/orders", "/documents", "/login", "/register",
)
def register_security_headers(app):
    @app.after_request
    def add_security_headers(response):
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = PERMISSIONS_POLICY
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # HSTS only makes sense over HTTPS (never send it on plain http://localhost).
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = HSTS

        # Pages for logged-in users must not be stored by shared caches.
        if response.mimetype == "text/html":
            response.headers.setdefault("Cache-Control", "no-store")

        if request.path.startswith(PRIVATE_PREFIXES):
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response