"""Centralised HTTP error handlers.

API requests (``/api/*``) always receive JSON in the shape
``{"error": ..., "code": ...}``. Browser page requests receive friendly HTML
error pages. Internal exception text is never leaked to clients.
"""

from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from app.core.exceptions import AppError


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.is_json


def register_error_handlers(app):

    @app.errorhandler(AppError)
    def handle_app_error(e: AppError):
        return jsonify(e.to_dict()), e.status

    def _render(status: int, title: str, message: str, json_message: str, code: str):
        if _wants_json():
            return jsonify({"error": json_message, "code": code}), status
        return render_template(f"errors/{status}.html", title=title, message=message), status

    @app.errorhandler(400)
    def bad_request(e):
        # CSRFError is a 400 subclass
        desc = getattr(e, "description", "") or "Bad request"
        if _wants_json():
            return jsonify({"error": desc, "code": "bad_request"}), 400
        return render_template("errors/400.html", title="Bad request", message=desc), 400

    @app.errorhandler(403)
    def forbidden(e):
        return _render(403, "Access denied", "You don't have permission to view this.",
                       "You do not have permission to access this resource.", "forbidden")

    @app.errorhandler(404)
    def not_found(e):
        return _render(404, "Page not found", "We couldn't find what you were looking for.",
                       "Endpoint not found", "not_found")

    @app.errorhandler(405)
    def method_not_allowed(e):
        if _wants_json():
            return jsonify({"error": "Method not allowed", "code": "method_not_allowed"}), 405
        return render_template("errors/404.html", title="Not allowed",
                               message="That action isn't supported here."), 405

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large. Maximum size is 5MB.", "code": "file_too_large"}), 413

    @app.errorhandler(429)
    def rate_limited(e):
        if _wants_json():
            return jsonify({"error": "Too many requests. Please slow down and try again shortly.",
                            "code": "rate_limited"}), 429
        return render_template("errors/429.html", title="Slow down",
                               message="Too many requests. Please try again in a moment."), 429

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.exception("Unhandled server error")
        try:
            from app.extensions import db
            db.session.rollback()
        except Exception:  # pragma: no cover
            pass
        return _render(500, "Something went wrong", "An unexpected error occurred. Please try again.",
                       "Internal server error", "internal_error")

    @app.errorhandler(Exception)
    def unhandled(e):
        if isinstance(e, HTTPException):
            return e
        return internal_error(e)
