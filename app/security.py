"""Security helpers: the admin check and the HTTP security headers."""

from flask import abort, request
from flask_login import current_user

from app.extensions import login_manager

# Content Security Policy: the browser only loads scripts, styles, fonts and images
# from our own site (plus Google's reCAPTCHA). Inline <script> and style="..." are
# blocked, so even injected HTML could not run JavaScript (XSS protection).
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "frame-src https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/",
        "form-action 'self' https://checkout.stripe.com",  # the redirect to Stripe's payment page
        "frame-ancestors 'none'",  # no other site may show our pages in a frame
        "base-uri 'self'",
        "object-src 'none'",
    ]
)


def check_admin():
    """Runs before every route of the admin blueprint (see routes/admin.py):
    anonymous visitors go to the login page, customers get 403 Forbidden."""
    if not current_user.is_authenticated:
        return login_manager.unauthorized()  # redirect to /login?next=...
    if not current_user.is_admin:
        abort(403)
    return None  # an admin: Flask continues with the route


def add_security_headers(response):
    """after_request: the headers checked by securityheaders.com (grade A)."""
    response.headers["Content-Security-Policy"] = CSP
    response.headers["X-Content-Type-Options"] = "nosniff"  # no guessing of file types
    response.headers["X-Frame-Options"] = "DENY"  # older browsers: no framing (clickjacking)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # HSTS: "use only HTTPS for this site for a year". Only sent over HTTPS
    # (behind Render's proxy this works thanks to ProxyFix in create_app).
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
