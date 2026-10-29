"""
ResumeAI — AI Resume & Career Copilot
Application factory.

Builds and configures the Flask application: loads environment variables,
applies configuration, initialises extensions (PostgreSQL via SQLAlchemy,
migrations, auth, CSRF, rate limiting), registers blueprints, security headers
and centralised error handling.
"""

import os
import secrets

from flask import Flask, g, request
from flask_login import current_user

from app.config import config_map
from app.core.errors import register_error_handlers
from app.core.logging_config import configure_logging
from app.extensions import csrf, db, limiter, login_manager, migrate


def create_app(env: str | None = None) -> Flask:
    """Application factory.

    Args:
        env: "development" | "production" | "testing". Defaults to the FLASK_ENV
             environment variable (or "development" if unset).
    """
    env = env or os.getenv("FLASK_ENV", "default")
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    config_class = config_map.get(env, config_map["default"])
    app.config.from_object(config_class)
    config_class.init_app(app)

    if os.getenv("TRUST_PROXY", "").lower() in {"1", "true", "yes"}:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    configure_logging(app)

    # Extensions
    db.init_app(app)
    from app import models  # noqa: F401  (register tables with SQLAlchemy metadata)
    migrate.init_app(app, db, compare_type=True)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(models.User, int(user_id))
        except (TypeError, ValueError):
            return None
        return user if user and user.is_active else None

    # Blueprints
    from app.blueprints.account import account_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.career import career_bp
    from app.blueprints.history import history_bp
    from app.blueprints.interview import interview_bp
    from app.blueprints.pages import pages_bp
    from app.blueprints.resume import resume_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(resume_bp, url_prefix="/api")
    app.register_blueprint(interview_bp, url_prefix="/api")
    app.register_blueprint(career_bp, url_prefix="/api")
    app.register_blueprint(history_bp, url_prefix="/api")

    register_error_handlers(app)
    _register_request_hooks(app)

    app.logger.info("ResumeAI app created (env=%s)", config_class.ENV_NAME)
    return app


def _register_request_hooks(app: Flask) -> None:
    @app.before_request
    def _nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def _inject():
        ctx = {"csp_nonce": getattr(g, "csp_nonce", ""), "credit_costs": app.config["CREDIT_COSTS"],
               "initial_credits": app.config["INITIAL_USER_CREDITS"]}
        if current_user.is_authenticated:
            from app.services.credit_service import get_balance
            ctx["credit_balance"] = get_balance(current_user.id)
            ctx["user_theme"] = current_user.theme
        else:
            ctx["credit_balance"], ctx["user_theme"] = None, ""
        return ctx

    @app.after_request
    def _security_headers(resp):
        nonce = getattr(g, "csp_nonce", "")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        resp.headers.setdefault("Content-Security-Policy", (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none'"))
        if request.is_secure or app.config.get("SESSION_COOKIE_SECURE"):
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Authenticated pages / API data must never be cached by shared caches
        if request.path.startswith("/api/") or current_user.is_authenticated:
            resp.headers.setdefault("Cache-Control", "private, no-store")
        return resp
