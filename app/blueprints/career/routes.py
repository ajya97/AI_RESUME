"""
Career API: job matching, skill-gap analysis, saved reports, resume chatbot.

POST   /api/job-match                      {resume_id, job_description}            billable: job_match
POST   /api/skill-gap                      {resume_id, target_role, requirements?} billable: skill_gap
GET    /api/career/roles                   role catalogue
GET    /api/reports/<id>                   a saved report (owner only)
DELETE /api/reports/<id>
GET    /api/reports/<id>/export.pdf
PATCH  /api/reports/<id>/progress          {skill, status}  (self-reported learning progress)
POST   /api/chat/sessions                  {resume_id}
GET    /api/chat/sessions?resume_id=
GET    /api/chat/sessions/<id>
DELETE /api/chat/sessions/<id>
POST   /api/chat/sessions/<id>/messages    {message}        billable: chat_message
"""

import copy
import io
from types import SimpleNamespace

from flask import current_app, jsonify, request, send_file
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.blueprints.career import career_bp
from app.core.exceptions import NotFoundError, ValidationError
from app.core.http import idempotency_key, json_body
from app.extensions import db, limiter
from app.models.chat import ChatMessage, ChatSession
from app.models.resume import Report
from app.services import chat_service, credit_service, export_service, job_match_service, report_service
from app.services import resume_service, skill_gap_service
from app.services.credit_service import billable
from app.services.skill_catalog import ROLE_SKILLS


def _credits(op: str) -> dict:
    return {"charged": current_app.config["CREDIT_COSTS"][op],
            "balance": credit_service.get_balance(current_user.id)}


def serialize_report(r: Report) -> dict:
    return {"id": r.id, "type": r.type, "title": r.title, "score": r.score, "status": r.status,
            "resume_id": r.resume_id, "created_at": r.created_at.isoformat(),
            "inputs": r.inputs, "data": r.data}


def get_owned_report(user_id: int, report_id: int) -> Report:
    r = db.session.execute(select(Report).where(Report.id == report_id, Report.user_id == user_id)).scalar_one_or_none()
    if r is None:
        raise NotFoundError("Report not found.")
    return r


# ─── Job match & skill gap ────────────────────────────────────────────────
@career_bp.route("/job-match", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def job_match():
    body = json_body()
    resume = resume_service.get_owned_resume(current_user.id, body.get("resume_id"))
    jd = job_match_service.clean_job_description(body.get("job_description"))
    if len(jd) > current_app.config["MAX_JOB_DESCRIPTION_CHARS"]:
        raise ValidationError(f"Job description is too long (max {current_app.config['MAX_JOB_DESCRIPTION_CHARS']} characters).")
    report = report_service.run_job_match(current_user, resume, jd, idempotency_key())
    return jsonify({"success": True, "report": serialize_report(report), "credits": _credits("job_match")})


@career_bp.route("/skill-gap", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def skill_gap():
    body = json_body()
    resume = resume_service.get_owned_resume(current_user.id, body.get("resume_id"))
    role = skill_gap_service.clean_target_role(body.get("target_role"))
    reqs = body.get("requirements") or ""
    if not isinstance(reqs, str) or len(reqs) > current_app.config["MAX_JOB_DESCRIPTION_CHARS"]:
        raise ValidationError("Requirements must be text under the length limit.")
    report = report_service.run_skill_gap(current_user, resume, role, reqs.strip(), idempotency_key())
    return jsonify({"success": True, "report": serialize_report(report), "credits": _credits("skill_gap")})


@career_bp.route("/career/roles", methods=["GET"])
@login_required
def roles():
    return jsonify({"roles": list(ROLE_SKILLS.keys())})


# ─── Reports ──────────────────────────────────────────────────────────────
@career_bp.route("/reports/<int:report_id>", methods=["GET"])
@login_required
def get_report(report_id):
    return jsonify({"report": serialize_report(get_owned_report(current_user.id, report_id))})


@career_bp.route("/reports/<int:report_id>", methods=["DELETE"])
@login_required
def delete_report(report_id):
    db.session.delete(get_owned_report(current_user.id, report_id))
    db.session.commit()
    return jsonify({"success": True})


@career_bp.route("/reports/<int:report_id>/export.pdf", methods=["GET"])
@login_required
def export_report(report_id):
    r = get_owned_report(current_user.id, report_id)
    pdf = export_service.report_pdf(r, current_user.display_name)
    name = resume_service.safe_download_name(f"{r.type}-report-{r.id}", "pdf")
    resp = send_file(io.BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name=name)
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


@career_bp.route("/reports/<int:report_id>/progress", methods=["PATCH"])
@login_required
def update_progress(report_id):
    r = get_owned_report(current_user.id, report_id)
    if r.type != "skill_gap":
        raise ValidationError("Progress tracking is only available for skill-gap reports.")
    body = json_body()
    skill, status = body.get("skill"), body.get("status")
    if status not in ("todo", "in_progress", "done"):
        raise ValidationError("Status must be todo, in_progress or done.")
    data = copy.deepcopy(r.data)
    for item in data.get("plan", {}).get("learning_plan", []):
        if item.get("skill") == skill:
            item["status"] = status
            r.data = data  # reassign so the JSONB change is detected
            db.session.commit()
            return jsonify({"success": True, "skill": skill, "status": status,
                            "note": "Progress is self-reported; it is not verified."})
    raise NotFoundError("Skill not found in this plan.")


# ─── Resume chatbot ───────────────────────────────────────────────────────
def get_owned_chat(user_id: int, session_id: int) -> ChatSession:
    s = db.session.execute(select(ChatSession).where(ChatSession.id == session_id,
                                                     ChatSession.user_id == user_id)).scalar_one_or_none()
    if s is None:
        raise NotFoundError("Chat not found.")
    return s


def _msg(m: ChatMessage) -> dict:
    return {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}


@career_bp.route("/chat/sessions", methods=["POST"])
@login_required
def create_chat():
    resume = resume_service.get_owned_resume(current_user.id, json_body().get("resume_id"))
    s = ChatSession(user_id=current_user.id, resume_id=resume.id)
    db.session.add(s)
    db.session.commit()
    return jsonify({"success": True, "session": {"id": s.id, "title": s.title, "resume_id": s.resume_id}}), 201


@career_bp.route("/chat/sessions", methods=["GET"])
@login_required
def list_chats():
    stmt = select(ChatSession).where(ChatSession.user_id == current_user.id)
    rid = request.args.get("resume_id", type=int)
    if rid:
        stmt = stmt.where(ChatSession.resume_id == rid)
    rows = db.session.execute(stmt.order_by(ChatSession.updated_at.desc()).limit(50)).scalars().all()
    return jsonify({"sessions": [{"id": s.id, "title": s.title, "resume_id": s.resume_id,
                                  "updated_at": s.updated_at.isoformat()} for s in rows]})


@career_bp.route("/chat/sessions/<int:session_id>", methods=["GET"])
@login_required
def get_chat(session_id):
    s = get_owned_chat(current_user.id, session_id)
    return jsonify({"session": {"id": s.id, "title": s.title, "resume_id": s.resume_id,
                                "resume_filename": s.resume.original_filename},
                    "messages": [_msg(m) for m in s.messages],
                    "limit": current_app.config["MAX_CHAT_MESSAGES_PER_SESSION"]})


@career_bp.route("/chat/sessions/<int:session_id>", methods=["DELETE"])
@login_required
def delete_chat(session_id):
    db.session.delete(get_owned_chat(current_user.id, session_id))
    db.session.commit()
    return jsonify({"success": True})


@career_bp.route("/chat/sessions/<int:session_id>/messages", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def send_chat_message(session_id):
    s = get_owned_chat(current_user.id, session_id)
    text = json_body().get("message")
    if not isinstance(text, str) or not text.strip():
        raise ValidationError("Please type a message.")
    text = text.strip()
    max_chars = current_app.config["MAX_CHAT_MESSAGE_CHARS"]
    if len(text) > max_chars:
        raise ValidationError(f"Message is too long (max {max_chars} characters).")
    count = db.session.execute(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == s.id)).scalar_one()
    if count >= current_app.config["MAX_CHAT_MESSAGES_PER_SESSION"]:
        raise ValidationError("This conversation reached its message limit. Start a new chat.", code="chat_limit")

    resume, sid = s.resume, s.id
    history = [SimpleNamespace(role=m.role, content=m.content) for m in s.messages]
    with billable(current_user.id, "chat_message", idempotency_key=idempotency_key(),
                  description="Resume chatbot message") as tx:
        reply = chat_service.generate_reply(current_user.id, resume, history, text)
        if not reply:
            from app.core.exceptions import AIOutputError
            raise AIOutputError("The assistant returned an empty reply. Your credits were refunded.")
        sess = db.session.get(ChatSession, sid)
        um = ChatMessage(session_id=sid, role="user", content=text, credit_tx_id=tx.id)
        am = ChatMessage(session_id=sid, role="assistant", content=reply, credit_tx_id=tx.id)
        db.session.add_all([um, am])
        if count == 0:
            sess.title = text[:60]
        sess.updated_at = db.func.now()
        db.session.commit()
    return jsonify({"success": True, "user_message": _msg(um), "message": _msg(am),
                    "credits": _credits("chat_message")})
