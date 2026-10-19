from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user

from app.extensions import db
from app.models import User
from app.validators import is_valid_email, is_valid_password, is_valid_phone

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
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

    flash("Account created. You can log in now.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None, email="")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        # Same message for "unknown email" and "wrong password",
        # so an attacker cannot discover which emails are registered.
        return render_template(
            "login.html", error="Invalid email or password.", email=email
        ), 401

    login_user(user)
    flash("Logged in.", "success")
    return redirect(url_for("main.index"))


@bp.post("/logout")
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("main.index"))