"""Centralized logging setup for the application."""

import logging
import sys


def configure_logging(app):
    """Attach a simple, consistent formatter to the Flask app logger."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    handler.setFormatter(formatter)

    app.logger.handlers = [handler]
    app.logger.setLevel(logging.DEBUG if app.config.get("DEBUG") else logging.INFO)
