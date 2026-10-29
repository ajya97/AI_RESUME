from flask import Blueprint

career_bp = Blueprint("career", __name__)

from app.blueprints.career import routes  # noqa: E402,F401
