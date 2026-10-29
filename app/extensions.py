"""Flask extension singletons (initialised in the application factory)."""

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()


def _rate_key():
    """Rate-limit per authenticated user when possible, else per IP."""
    if current_user and current_user.is_authenticated:
        return f"user:{current_user.get_id()}"
    return get_remote_address()


limiter = Limiter(key_func=_rate_key)

login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "info"
login_manager.session_protection = "strong"


@login_manager.unauthorized_handler
def _unauthorized():
    from flask import jsonify, redirect, url_for

    if request.path.startswith("/api/"):
        return jsonify({"error": "Authentication required.", "code": "auth_required"}), 401
    return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
