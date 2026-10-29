"""Authentication: register, login, logout, forgot/reset password."""

import hashlib
import re
from urllib.parse import urlparse

from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.blueprints.auth import auth_bp
from app.core.mail import mail_configured, send_email
from app.extensions import db, limiter
from app.models.mixins import utcnow
from app.models.user import User
from app.services.credit_service import grant_initial_credits

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
# Used to keep login timing similar for unknown emails
_DUMMY_HASH = "scrypt:32768:8:1$dummy$" + "0" * 128


def validate_password(password: str, email: str = "") -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password) > 128:
        return "Password must be at most 128 characters."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "Password must contain at least one letter and one number."
    if email and password.lower() == email.lower():
        return "Password must not be the same as your email."
    return None


def _safe_next(target: str | None) -> str | None:
    if not target:
        return None
    p = urlparse(target)
    if p.scheme or p.netloc or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    return target


def _email_key():
    return (request.form.get("email") or "").strip().lower() or request.remote_addr


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"], error_message="Too many sign-up attempts. Try again later.")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))
    if request.method == "POST":
        name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        theme = request.form.get("theme") if request.form.get("theme") in ("dark", "light") else "dark"

        error = None
        if not name or len(name) > 120:
            error = "Please enter your name (max 120 characters)."
        elif not EMAIL_RE.match(email) or len(email) > 254:
            error = "Please enter a valid email address."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            error = validate_password(password, email)
        if not error and db.session.execute(select(User.id).where(User.email == email)).first():
            error = "An account with this email already exists."
        if error:
            flash(error, "error")
            return render_template("auth/register.html", form={"full_name": name, "email": email}), 400

        user = User(email=email, full_name=name, theme=theme)
        user.set_password(password)
        try:
            db.session.add(user)
            db.session.flush()
            grant_initial_credits(user)  # wallet + exactly one welcome grant, same transaction
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("An account with this email already exists.", "error")
            return render_template("auth/register.html", form={"full_name": name, "email": email}), 400

        session.clear()
        login_user(user)
        session.permanent = True
        flash(f"Welcome! {current_app.config['INITIAL_USER_CREDITS']} credits have been added to your account.", "success")
        return redirect(url_for("pages.dashboard"))
    return render_template("auth/register.html", form={})


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute", methods=["POST"], error_message="Too many sign-in attempts. Try again shortly.")
@limiter.limit("8 per 15 minutes", methods=["POST"], key_func=_email_key,
               error_message="Too many failed attempts for this account. Try again in a few minutes.")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))
    nxt = _safe_next(request.values.get("next"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        ok = False
        if user:
            ok = user.check_password(password) and user.is_active
        else:
            from werkzeug.security import check_password_hash
            check_password_hash(_DUMMY_HASH, password)  # equalise timing
        if not ok:
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html", form={"email": email}, next=nxt), 401
        session.clear()
        login_user(user, remember=bool(request.form.get("remember")))
        session.permanent = True
        user.last_login_at = utcnow()
        db.session.commit()
        return redirect(nxt or url_for("pages.dashboard"))
    return render_template("auth/login.html", form={}, next=nxt)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("pages.index"))


# ─── Password reset ───────────────────────────────────────────────────────
def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")


def _fingerprint(user: User) -> str:
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def make_reset_token(user: User) -> str:
    return _serializer().dumps({"uid": user.id, "fp": _fingerprint(user)})


def load_reset_user(token: str) -> User | None:
    try:
        data = _serializer().loads(token, max_age=current_app.config["PASSWORD_RESET_MAX_AGE"])
    except BadData:
        return None
    user = db.session.get(User, data.get("uid"))
    # fingerprint ties the token to the CURRENT password hash => single use
    if user and data.get("fp") == _fingerprint(user):
        return user
    return None


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"], key_func=_email_key)
@limiter.limit("20 per hour", methods=["POST"])
def forgot_password():
    configured = mail_configured()
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user:
            base = current_app.config["APP_BASE_URL"] or request.host_url.rstrip("/")
            link = f"{base}{url_for('auth.reset_password', token=make_reset_token(user))}"
            if configured:
                try:
                    minutes = current_app.config["PASSWORD_RESET_MAX_AGE"] // 60
                    send_email(user.email, "Reset your ResumeAI password",
                               f"Use this link to reset your password (valid for {minutes} minutes):\n\n{link}\n\n"
                               "If you didn't request this, you can ignore this email.")
                except Exception:
                    current_app.logger.exception("Password reset email failed")
            elif current_app.debug:
                # Developer convenience ONLY in debug mode; never in production.
                current_app.logger.warning("MAIL not configured. DEV reset link for %s: %s", user.email, link)
        if configured:
            flash("If an account exists for that email, a reset link has been sent.", "info")
        else:
            flash("Password-reset email is not configured on this server, so no email was sent. "
                  "Ask the administrator to set the MAIL_* variables.", "error")
        return redirect(url_for("auth.forgot_password"))
    return render_template("auth/forgot_password.html", configured=configured)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("20 per hour", methods=["POST"])
def reset_password(token):
    user = load_reset_user(token)
    if not user:
        flash("This reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        pw = request.form.get("password") or ""
        if pw != (request.form.get("confirm_password") or ""):
            flash("Passwords do not match.", "error")
        else:
            err = validate_password(pw, user.email)
            if err:
                flash(err, "error")
            else:
                user.set_password(pw)
                db.session.commit()
                flash("Password updated. You can now sign in.", "success")
                return redirect(url_for("auth.login"))
        return render_template("auth/reset_password.html", token=token), 400
    return render_template("auth/reset_password.html", token=token)
