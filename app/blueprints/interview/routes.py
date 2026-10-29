"""
Interview API (login required, owner-checked, persisted).

POST   /api/generate-questions     {resume_id?, difficulty?, category?, job_description?}   billable: interview_session
POST   /api/evaluate-answer        {session_id, index, answer}                              billable: interview_evaluation
POST   /api/interview/<id>/skip    {index}
GET    /api/interview-summary?session_id=
GET    /api/interview/<id>         full session incl. saved answers
GET    /api/interview/sessions     recent sessions
POST   /api/interview/<id>/retry   clone questions into a fresh attempt (no new generation charge)
DELETE /api/interview/<id>

AI evaluations are practice feedback only — not objective or employer-approved assessments.
"""

from flask import current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.blueprints.interview import interview_bp
from app.core.exceptions import DuplicateOperationError, NotFoundError, ValidationError
from app.core.http import idempotency_key, json_body
from app.extensions import db, limiter
from app.models.interview import InterviewAnswer, InterviewSession
from app.models.mixins import utcnow
from app.models.resume import Resume
from app.services import credit_service, interview_service, resume_service
from app.services.credit_service import billable

DISCLAIMER = "AI feedback is for practice only and is not an objective or employer-approved assessment."


def _credits(op: str) -> dict:
    return {"charged": current_app.config["CREDIT_COSTS"][op], "balance": credit_service.get_balance(current_user.id)}


def get_owned_session(user_id: int, sid: int) -> InterviewSession:
    s = db.session.execute(select(InterviewSession).where(InterviewSession.id == sid,
                                                          InterviewSession.user_id == user_id)).scalar_one_or_none()
    if s is None:
        raise NotFoundError("Interview session not found.")
    return s


def _label(avg: float) -> str:
    return "Excellent" if avg >= 8 else "Good" if avg >= 6 else "Average" if avg >= 4 else "Needs Work"


def _refresh_progress(s: InterviewSession) -> None:
    answers = list(s.answers)
    if answers:
        s.avg_score = round(sum(a.score for a in answers) / len(answers), 1)
    if len(answers) >= len(s.questions) and s.status != "completed":
        s.status = "completed"
        s.completed_at = utcnow()


def _answer_dict(a: InterviewAnswer) -> dict:
    return {"index": a.question_index, "question": a.question, "category": a.category, "answer": a.answer,
            "skipped": a.skipped, "score": a.score, "evaluation": a.evaluation}


def serialize_session(s: InterviewSession, with_answers: bool = True) -> dict:
    d = {"id": s.id, "status": s.status, "difficulty": s.difficulty, "focus": s.focus_category,
         "target_role": s.target_role, "candidate_name": (s.resume.parsed or {}).get("name", "Candidate"),
         "resume_id": s.resume_id, "total_questions": len(s.questions), "answered": len(s.answers),
         "average_score": s.avg_score, "created_at": s.created_at.isoformat(), "questions": s.questions,
         "has_job_description": bool(s.job_description), "disclaimer": DISCLAIMER}
    if with_answers:
        d["answers"] = [_answer_dict(a) for a in s.answers]
    return d


@interview_bp.route("/generate-questions", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def generate_questions():
    """Create a persisted interview session with AI-generated questions."""
    body = request.get_json(silent=True) or {}
    if body.get("resume_id") is not None:
        resume = resume_service.get_owned_resume(current_user.id, body.get("resume_id"))
    else:  # original behaviour: use the most recently uploaded resume
        resume = db.session.execute(select(Resume).where(Resume.user_id == current_user.id)
                                    .order_by(Resume.created_at.desc()).limit(1)).scalar_one_or_none()
        if resume is None:
            raise ValidationError("No resume data found. Please upload your resume first.")

    difficulty = body.get("difficulty", "Mixed")
    if difficulty not in interview_service.DIFFICULTIES:
        raise ValidationError("Difficulty must be Easy, Medium, Hard or Mixed.")
    focus = body.get("category", "all")
    if focus != "all" and focus not in interview_service.CATEGORIES:
        raise ValidationError("Unknown question category.")
    jd = (body.get("job_description") or "").strip()
    if len(jd) > current_app.config["MAX_JOB_DESCRIPTION_CHARS"]:
        raise ValidationError("Job description is too long.")
    if jd and len(jd) < 40:
        raise ValidationError("Job description is too short to use (min 40 characters), or leave it empty.")

    parsed = dict(resume.parsed or {})
    with billable(current_user.id, "interview_session", idempotency_key=idempotency_key(),
                  description=f"Interview session: {resume.original_filename}") as tx:
        data = interview_service.generate_interview_questions(parsed, difficulty, jd or None)
        questions = data["questions"]
        if focus != "all":
            only = [q for q in questions if q.get("category") == focus]
            questions = only or questions
        sess = InterviewSession(
            user_id=current_user.id, resume_id=resume.id, difficulty=difficulty, focus_category=focus,
            target_role=(data.get("target_role") or "")[:200], job_description=jd or None,
            questions=questions, credit_tx_id=tx.id)
        db.session.add(sess)
        db.session.commit()
    return jsonify({"success": True, "session_id": sess.id, "candidate_name": data.get("candidate_name") or
                    parsed.get("name", "Candidate"), "target_role": sess.target_role, "questions": questions,
                    "difficulty": difficulty, "focus": focus, "credits": _credits("interview_session"),
                    "disclaimer": DISCLAIMER})


@interview_bp.route("/evaluate-answer", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def evaluate():
    """Evaluate one answer (the question text is read from the DB, never trusted from the browser)."""
    body = json_body()
    s = get_owned_session(current_user.id, body.get("session_id"))
    try:
        idx = int(body.get("index"))
    except (TypeError, ValueError):
        raise ValidationError("A valid question index is required.")
    if not 0 <= idx < len(s.questions):
        raise ValidationError("Question index out of range.")
    answer = (body.get("answer") or "").strip() if isinstance(body.get("answer"), str) else ""
    if not answer:
        raise ValidationError("Question and answer are required")
    if len(answer) < 10:
        raise ValidationError("Answer is too short. Please provide a meaningful response.")
    if len(answer) > current_app.config["MAX_INTERVIEW_ANSWER_CHARS"]:
        raise ValidationError(f"Answer is too long (max {current_app.config['MAX_INTERVIEW_ANSWER_CHARS']} characters).")
    if any(a.question_index == idx for a in s.answers):
        raise DuplicateOperationError("This question was already answered.")

    q = s.questions[idx]
    parsed, sid = dict(s.resume.parsed or {}), s.id
    with billable(current_user.id, "interview_evaluation", idempotency_key=idempotency_key(),
                  description=f"Answer evaluation (Q{idx + 1})") as tx:
        ev = interview_service.evaluate_answer(q["question"], answer, q.get("category", "General"), parsed)
        db.session.add(InterviewAnswer(session_id=sid, question_index=idx, question=q["question"],
                                       category=q.get("category", "General"), answer=answer,
                                       score=ev["score"], evaluation=ev, credit_tx_id=tx.id))
        db.session.flush()
        s = db.session.get(InterviewSession, sid)
        db.session.refresh(s)
        _refresh_progress(s)
        db.session.commit()
    return jsonify({"success": True, "evaluation": ev, "disclaimer": DISCLAIMER,
                    "progress": {"answered": len(s.answers), "total": len(s.questions),
                                 "average_score": s.avg_score, "status": s.status},
                    "credits": _credits("interview_evaluation")})


@interview_bp.route("/interview/<int:sid>/skip", methods=["POST"])
@login_required
def skip(sid):
    s = get_owned_session(current_user.id, sid)
    try:
        idx = int(json_body().get("index"))
    except (TypeError, ValueError):
        raise ValidationError("A valid question index is required.")
    if not 0 <= idx < len(s.questions):
        raise ValidationError("Question index out of range.")
    if any(a.question_index == idx for a in s.answers):
        raise DuplicateOperationError("This question was already answered.")
    q = s.questions[idx]
    try:
        db.session.add(InterviewAnswer(session_id=s.id, question_index=idx, question=q["question"],
                                       category=q.get("category", "General"), skipped=True, score=0))
        db.session.flush()
        db.session.refresh(s)
        _refresh_progress(s)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise DuplicateOperationError("This question was already answered.")
    return jsonify({"success": True, "progress": {"answered": len(s.answers), "total": len(s.questions),
                                                  "average_score": s.avg_score, "status": s.status}})


@interview_bp.route("/interview-summary", methods=["GET"])
@login_required
def interview_summary():
    sid = request.args.get("session_id", type=int)
    if sid:
        s = get_owned_session(current_user.id, sid)
    else:
        s = db.session.execute(select(InterviewSession).where(InterviewSession.user_id == current_user.id)
                               .order_by(InterviewSession.id.desc()).limit(1)).scalar_one_or_none()
    if s is None or not s.answers:
        return jsonify({"error": "No interview data found", "code": "not_found"}), 404
    scores = [a.score for a in s.answers]
    avg = round(sum(scores) / len(scores), 1)
    return jsonify({
        "session_id": s.id, "status": s.status,
        "candidate_name": (s.resume.parsed or {}).get("name", "Candidate"),
        "total_questions_answered": len(scores), "total_questions": len(s.questions),
        "average_score": avg, "score_label": _label(avg), "individual_scores": scores,
        "breakdown": [{"index": a.question_index, "category": a.category, "score": a.score, "skipped": a.skipped}
                      for a in s.answers],
        "disclaimer": DISCLAIMER})


@interview_bp.route("/interview/sessions", methods=["GET"])
@login_required
def list_sessions():
    rows = db.session.execute(select(InterviewSession).where(InterviewSession.user_id == current_user.id)
                              .order_by(InterviewSession.id.desc()).limit(30)).scalars().all()
    return jsonify({"sessions": [serialize_session(s, with_answers=False) for s in rows]})


@interview_bp.route("/interview/<int:sid>", methods=["GET"])
@login_required
def get_session(sid):
    return jsonify({"session": serialize_session(get_owned_session(current_user.id, sid))})


@interview_bp.route("/interview/<int:sid>/retry", methods=["POST"])
@login_required
def retry(sid):
    old = get_owned_session(current_user.id, sid)
    new = InterviewSession(user_id=old.user_id, resume_id=old.resume_id, difficulty=old.difficulty,
                           focus_category=old.focus_category, target_role=old.target_role,
                           job_description=old.job_description, questions=old.questions)
    db.session.add(new)
    db.session.commit()
    return jsonify({"success": True, "session_id": new.id, "questions": new.questions,
                    "target_role": new.target_role})


@interview_bp.route("/interview/<int:sid>", methods=["DELETE"])
@login_required
def delete_session(sid):
    db.session.delete(get_owned_session(current_user.id, sid))
    db.session.commit()
    return jsonify({"success": True})
