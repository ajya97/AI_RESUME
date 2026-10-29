from flask import Blueprint

interview_bp = Blueprint("interview", __name__)

from app.blueprints.interview import routes  # noqa: E402,F401
