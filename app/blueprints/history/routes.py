"""
GET /api/history?type=&q=&page=&per_page=   unified, paginated activity list (own data only)
GET /api/analytics/summary                   dashboard metrics computed from real records
"""

from flask import jsonify, request
from flask_login import current_user, login_required

from app.blueprints.history import history_bp
from app.core.http import page_args
from app.services import history_service


@history_bp.route("/history", methods=["GET"])
@login_required
def history():
    page, per = page_args(10, 50)
    kind = request.args.get("type") or None
    q = (request.args.get("q") or "").strip()[:100] or None
    return jsonify(history_service.list_history(current_user.id, kind, q, page, per))


@history_bp.route("/analytics/summary", methods=["GET"])
@login_required
def analytics():
    return jsonify(history_service.analytics(current_user.id))
