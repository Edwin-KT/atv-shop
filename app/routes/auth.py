from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from app.extensions import db, limiter
from app.models import User
from app.services.audit import record_event
from app.validators import is_valid_email, is_valid_password, is_valid_phone

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", errors=[], email="", phone="")

    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")

    errors = []
    if not is_valid_email(email):
        errors.append("Invalid email address.")
    if not is_valid_phone(phone):
        errors.append("Phone number must have exactly 10 digits.")
    if not is_valid_password(password):
        errors.append("Password must have at least 8 characters.")
    if not errors and User.query.filter_by(email=email).first():
        errors.append("An account with this email already exists.")

    if errors:
        return render_template(
            "register.html", errors=errors, email=email, phone=phone
        ), 400

    user = User(email=email, phone=phone)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    record_event("user_registered", user_id=user.id)
    flash("Account created. You can log in now.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None, email="")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        # !r escapes newlines: stops "log injection" (a user typing fake log lines)
        record_event(
            "login_failed",
            user_id=user.id if user else None,
            details=f"email={email[:100]!r}",
        )
        return render_template(
            "login.html", error="Invalid email or password.", email=email
        ), 401

    login_user(user)
    record_event("login_success", user_id=user.id)
    flash("Logged in.", "success")
    return redirect(url_for("main.index"))


@bp.post("/logout")
def logout():
    if current_user.is_authenticated:
        record_event("logout", user_id=current_user.id)  # before logout_user()
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("main.index"))