"""Server-rendered pages. Public: landing + features. Everything else needs login."""

from flask import abort, current_app, jsonify, render_template, send_file
from flask_login import current_user, login_required
from sqlalchemy import select, text

from app.blueprints.pages import pages_bp
from app.extensions import db
from app.models.chat import ChatSession
from app.models.interview import InterviewSession
from app.models.resume import Report
from app.services import resume_service, template_service


@pages_bp.route("/")
def index():
    return render_template("index.html")


@pages_bp.route("/features")
def features():
    return render_template("features.html")


@pages_bp.route("/healthz")
def healthz():
    """Liveness + database connectivity probe (no secrets, no user data)."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "up"})
    except Exception:
        current_app.logger.exception("health check: database unreachable")
        return jsonify({"status": "degraded", "database": "down"}), 503


@pages_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard/dashboard.html")


@pages_bp.route("/analyze")
@login_required
def analyze():
    """Resume upload & ATS analysis page."""
    return render_template("resume/upload.html")


@pages_bp.route("/templates")
@login_required
def templates_page():
    return render_template("resume/templates.html", templates=template_service.list_templates())


@pages_bp.route("/job-match")
@login_required
def job_match():
    return render_template("career/job_match.html")


@pages_bp.route("/skill-gap")
@login_required
def skill_gap():
    return render_template("career/skill_gap.html")


@pages_bp.route("/interview")
@login_required
def interview():
    """Interactive interview page."""
    return render_template("career/interview.html")


@pages_bp.route("/chatbot")
@login_required
def chatbot():
    return render_template("career/chatbot.html")


@pages_bp.route("/history")
@login_required
def history():
    return render_template("history/history.html")


@pages_bp.route("/history/<kind>/<int:item_id>")
@login_required
def history_detail(kind, item_id):
    """Report / session detail shell; data is fetched from the owner-checked API."""
    uid = current_user.id
    if kind in ("ats", "job_match", "skill_gap"):
        ok = db.session.execute(select(Report.id).where(Report.id == item_id, Report.user_id == uid,
                                                        Report.type == kind)).first()
    elif kind == "interview":
        ok = db.session.execute(select(InterviewSession.id).where(InterviewSession.id == item_id,
                                                                  InterviewSession.user_id == uid)).first()
    elif kind == "chat":
        ok = db.session.execute(select(ChatSession.id).where(ChatSession.id == item_id,
                                                             ChatSession.user_id == uid)).first()
    else:
        ok = None
    if not ok:
        abort(404)
    return render_template("history/report_detail.html", kind=kind, item_id=item_id)


@pages_bp.route("/resumes/<int:resume_id>/file")
@login_required
def resume_file(resume_id):
    """Authorised download of the user's own stored PDF (never served from /static)."""
    r = resume_service.get_owned_resume(current_user.id, resume_id)
    path = resume_service.resume_path(r)
    if not path.exists():
        abort(404)
    resp = send_file(path, mimetype="application/pdf", as_attachment=True, download_name=r.original_filename)
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@pages_bp.route("/resumes/<int:resume_id>/preview/<key>")
@login_required
def resume_preview(resume_id, key):
    """HTML preview of the resume in a chosen template (loaded in a sandboxed iframe).
    Jinja autoescaping neutralises any HTML/script in user-supplied content."""
    r = resume_service.get_owned_resume(current_user.id, resume_id)
    if not template_service.is_valid(key):
        abort(404)
    content = r.content or resume_service.build_content(r.parsed)
    return render_template("resume/render.html", c=content, key=key, spec=template_service.TEMPLATES[key],
                           sections=template_service.SECTION_ORDER, split=template_service.split_entry,
                           contact=template_service.contact_line(content))
