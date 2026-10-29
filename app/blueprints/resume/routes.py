"""
Resume API (all routes require login; every resource is owner-checked).

POST   /api/upload                  upload + ATS analysis (original contract; billable: ats_analysis)
POST   /api/resumes                 upload only (free; stores + parses)
GET    /api/resumes                 list the user's resumes
DELETE /api/resumes/<id>            delete resume + stored PDF (+ derived reports/chats/interviews)
POST   /api/resumes/<id>/analyze    run ATS analysis on a stored resume (billable)
GET    /api/resumes/<id>/content    structured content for templates
PUT    /api/resumes/<id>/content    save edited content + chosen template
GET    /api/templates               template library
GET    /api/resumes/<id>/export.pdf?template=key   deterministic PDF export (free)
"""

from flask import current_app, jsonify, request, send_file
from flask_login import current_user, login_required
from sqlalchemy import select

from app.blueprints.resume import resume_bp
from app.core.exceptions import AppError, ResumeParsingError, ValidationError
from app.core.http import idempotency_key, json_body
from app.extensions import db, limiter
from app.models.resume import Report, Resume
from app.services import credit_service, export_service, report_service, resume_service, template_service


def serialize_resume(r: Resume, latest_score=None) -> dict:
    return {
        "id": r.id, "filename": r.original_filename, "size": r.file_size, "pages": r.page_count,
        "name": (r.parsed or {}).get("name", ""), "template": r.template_key,
        "uploaded_at": r.created_at.isoformat(), "latest_ats_score": latest_score,
    }


def _save_upload():
    try:
        return resume_service.save_upload(current_user, request.files.get("resume"))
    except ResumeParsingError as e:
        raise AppError(str(e), status=422, code="unreadable_pdf")


def serialize_ats(report: Report, resume: Resume, charged: int | None = None) -> dict:
    d = report.data
    return {
        "success": True, "resume_id": resume.id, "report_id": report.id,
        "parsed": d["parsed"], "ats": d["ats"], "missing_sections": d["missing_sections"],
        "errors": d["errors"], "gpt_analysis": d["gpt_analysis"], "ats_note": d.get("ats_note", ""),
        "credits": {"charged": charged, "balance": credit_service.get_balance(current_user.id)},
    }


@resume_bp.route("/upload", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def upload_resume():
    """Upload a PDF resume, parse it, run ATS scoring + AI analysis, return structured data."""
    resume, _dup = _save_upload()
    try:
        report = report_service.run_ats_analysis(current_user, resume, idempotency_key())
    except AppError as e:
        e.extra.setdefault("resume_id", resume.id)  # resume is saved; client can retry the analysis
        raise
    return jsonify(serialize_ats(report, resume, current_app.config["CREDIT_COSTS"]["ats_analysis"]))


@resume_bp.route("/resumes", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def create_resume():
    resume, dup = _save_upload()
    return jsonify({"success": True, "duplicate": dup, "resume": serialize_resume(resume)}), (200 if dup else 201)


@resume_bp.route("/resumes", methods=["GET"])
@login_required
def list_resumes():
    resumes = db.session.execute(select(Resume).where(Resume.user_id == current_user.id)
                                 .order_by(Resume.created_at.desc())).scalars().all()
    scores = {}
    for rid, score in db.session.execute(
            select(Report.resume_id, Report.score).where(Report.user_id == current_user.id, Report.type == "ats")
            .order_by(Report.created_at.asc())):
        scores[rid] = score
    return jsonify({"resumes": [serialize_resume(r, scores.get(r.id)) for r in resumes]})


@resume_bp.route("/resumes/<int:resume_id>", methods=["DELETE"])
@login_required
def delete_resume(resume_id):
    resume_service.delete_resume(resume_service.get_owned_resume(current_user.id, resume_id))
    return jsonify({"success": True})


@resume_bp.route("/resumes/<int:resume_id>/analyze", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def analyze_existing(resume_id):
    resume = resume_service.get_owned_resume(current_user.id, resume_id)
    report = report_service.run_ats_analysis(current_user, resume, idempotency_key())
    return jsonify(serialize_ats(report, resume, current_app.config["CREDIT_COSTS"]["ats_analysis"]))


@resume_bp.route("/resumes/<int:resume_id>/content", methods=["GET"])
@login_required
def get_content(resume_id):
    r = resume_service.get_owned_resume(current_user.id, resume_id)
    return jsonify({"content": r.content, "template": r.template_key, "templates": template_service.list_templates()})


@resume_bp.route("/resumes/<int:resume_id>/content", methods=["PUT"])
@login_required
def put_content(resume_id):
    r = resume_service.get_owned_resume(current_user.id, resume_id)
    body = json_body()
    r.content = resume_service.clean_content(body.get("content"))
    key = body.get("template", r.template_key)
    if not template_service.is_valid(key):
        raise ValidationError("Unknown template.")
    r.template_key = key
    db.session.commit()
    return jsonify({"success": True, "content": r.content, "template": r.template_key})


@resume_bp.route("/templates", methods=["GET"])
@login_required
def list_templates():
    return jsonify({"templates": template_service.list_templates()})


@resume_bp.route("/resumes/<int:resume_id>/export.pdf", methods=["GET"])
@login_required
def export_resume_pdf(resume_id):
    r = resume_service.get_owned_resume(current_user.id, resume_id)
    key = request.args.get("template", r.template_key)
    if not template_service.is_valid(key):
        raise ValidationError("Unknown template.")
    import io
    pdf = export_service.resume_pdf(r.content or resume_service.build_content(r.parsed), key)
    name = resume_service.safe_download_name((r.content or {}).get("name") or r.original_filename.rsplit(".", 1)[0], "pdf")
    resp = send_file(io.BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name=name)
    resp.headers["Cache-Control"] = "private, no-store"
    return resp
