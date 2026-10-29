"""History listing + dashboard analytics — everything computed from real rows."""

from sqlalchemy import Float, case, cast, func, literal, select, union_all

from app.extensions import db
from app.models.chat import ChatSession
from app.models.credits import AIUsage
from app.models.interview import InterviewSession
from app.models.resume import Report
from app.services import credit_service

KINDS = ("ats", "job_match", "skill_gap", "interview", "chat")
KIND_LABELS = {"ats": "ATS analysis", "job_match": "Job match", "skill_gap": "Skill gap",
               "interview": "Interview", "chat": "Resume chat"}


def _history_union(user_id: int):
    rep = select(
        Report.id.label("id"), Report.type.label("kind"), Report.title.label("title"),
        cast(Report.score, Float).label("score"), literal(100).label("score_max"),
        Report.status.label("status"), Report.created_at.label("created_at"),
    ).where(Report.user_id == user_id)
    iv = select(
        InterviewSession.id, literal("interview"),
        func.coalesce(func.nullif(InterviewSession.target_role, ""), "Interview session"),
        InterviewSession.avg_score, literal(10), InterviewSession.status, InterviewSession.created_at,
    ).where(InterviewSession.user_id == user_id)
    ch = select(
        ChatSession.id, literal("chat"), ChatSession.title,
        cast(literal(None), Float), literal(0), literal("completed"), ChatSession.created_at,
    ).where(ChatSession.user_id == user_id)
    return union_all(rep, iv, ch).subquery("history")


def list_history(user_id: int, kind: str | None, q: str | None, page: int, per_page: int) -> dict:
    h = _history_union(user_id)
    stmt = select(h)
    if kind in KINDS:
        stmt = stmt.where(h.c.kind == kind)
    if q:
        like = "%" + q.replace("%", r"\%").replace("_", r"\_") + "%"
        stmt = stmt.where(h.c.title.ilike(like, escape="\\"))
    total = db.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.session.execute(
        stmt.order_by(h.c.created_at.desc(), h.c.id.desc()).limit(per_page).offset((page - 1) * per_page)
    ).all()
    items = [{
        "id": r.id, "kind": r.kind, "kind_label": KIND_LABELS.get(r.kind, r.kind), "title": r.title,
        "score": None if r.score is None else round(float(r.score), 1), "score_max": r.score_max,
        "status": r.status, "created_at": r.created_at.isoformat(),
    } for r in rows]
    pages = max((total + per_page - 1) // per_page, 1)
    return {"items": items, "page": page, "per_page": per_page, "total": total, "pages": pages}


def analytics(user_id: int) -> dict:
    counts = dict(db.session.execute(
        select(Report.type, func.count()).where(Report.user_id == user_id).group_by(Report.type)).all())
    n_iv = db.session.execute(select(func.count()).select_from(InterviewSession)
                              .where(InterviewSession.user_id == user_id)).scalar_one()
    n_chat = db.session.execute(select(func.count()).select_from(ChatSession)
                                .where(ChatSession.user_id == user_id)).scalar_one()
    avg_ats = db.session.execute(select(func.avg(Report.score)).where(
        Report.user_id == user_id, Report.type == "ats")).scalar_one()

    ats_rows = db.session.execute(
        select(Report.id, Report.score, Report.created_at).where(Report.user_id == user_id, Report.type == "ats")
        .order_by(Report.created_at.desc()).limit(12)).all()
    ats_timeline = [{"id": r.id, "score": r.score, "date": r.created_at.date().isoformat()} for r in reversed(ats_rows)]

    gap_rows = db.session.execute(
        select(Report.id, Report.title, Report.score, Report.data, Report.created_at)
        .where(Report.user_id == user_id, Report.type == "skill_gap")
        .order_by(Report.created_at.desc()).limit(10)).all()
    gap_trend = [{"id": r.id, "title": r.title, "coverage": r.score,
                  "missing": len((r.data or {}).get("gap", {}).get("missing_skills", [])),
                  "date": r.created_at.date().isoformat()} for r in reversed(gap_rows)]

    iv_rows = db.session.execute(
        select(InterviewSession.id, InterviewSession.avg_score, InterviewSession.created_at)
        .where(InterviewSession.user_id == user_id, InterviewSession.status == "completed")
        .order_by(InterviewSession.created_at.desc()).limit(10)).all()
    iv_progress = [{"id": r.id, "avg": r.avg_score, "date": r.created_at.date().isoformat()} for r in reversed(iv_rows)]

    recent = list_history(user_id, None, None, 1, 6)["items"]

    tok = db.session.execute(select(
        func.coalesce(func.sum(AIUsage.input_tokens), 0), func.coalesce(func.sum(AIUsage.output_tokens), 0),
        func.sum(AIUsage.estimated_cost_usd)).where(AIUsage.user_id == user_id)).one()
    by_op = credit_service.usage_by_operation(user_id)

    return {
        "totals": {"ats": counts.get("ats", 0), "job_match": counts.get("job_match", 0),
                   "skill_gap": counts.get("skill_gap", 0), "interview": n_iv, "chat": n_chat,
                   "analyses": sum(counts.values())},
        "average_ats_score": None if avg_ats is None else round(float(avg_ats), 1),
        "ats_timeline": ats_timeline, "skill_gap_trend": gap_trend, "interview_progress": iv_progress,
        "recent_activity": recent,
        "credits": {"balance": credit_service.get_balance(user_id),
                    "spent_total": sum(o["credits"] for o in by_op), "by_operation": by_op},
        "ai_usage": {"input_tokens": int(tok[0]), "output_tokens": int(tok[1]),
                     "estimated_cost_usd": None if tok[2] is None else float(tok[2]),
                     "note": "Provider-reported token usage; separate from application credits."},
    }
