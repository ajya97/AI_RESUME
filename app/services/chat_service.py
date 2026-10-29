"""Resume chatbot: answers grounded in the selected resume + latest ATS report."""

from langchain_core.output_parsers import StrOutputParser
from sqlalchemy import select

from app.models.resume import Report
from app.extensions import db
from app.prompts.career_prompts import chat_prompt
from app.prompts.formatting import format_resume_for_chat
from app.services.llm_client import get_chat_model, invoke_chain

HISTORY_TURNS = 10


def analysis_context(user_id: int, resume_id: int) -> str:
    rep = db.session.execute(
        select(Report).where(Report.user_id == user_id, Report.resume_id == resume_id, Report.type == "ats")
        .order_by(Report.id.desc()).limit(1)).scalar_one_or_none()
    if not rep:
        return "No saved analysis for this resume."
    d = rep.data or {}
    ats = d.get("ats", {})
    gpt = d.get("gpt_analysis") or {}
    lines = [f"ATS heuristic score: {ats.get('total_score')}/100 ({ats.get('rating')})"]
    lines += [f"Tip: {t}" for t in (ats.get("top_tips") or [])[:6]]
    if gpt.get("target_role"):
        lines.append(f"Likely target role: {gpt['target_role']}")
    lines += [f"Missing critical skill: {s}" for s in (gpt.get("skill_gap_analysis", {}).get("missing_critical_skills") or [])[:6]]
    return "\n".join(lines)


def generate_reply(user_id: int, resume, history: list, message: str) -> str:
    llm = get_chat_model(temperature=0.5, max_tokens=800)
    chain = chat_prompt | llm | StrOutputParser()
    hist = "\n".join(f"{m.role}: {m.content}" for m in history[-HISTORY_TURNS * 2:]) or "(start of conversation)"
    reply = invoke_chain(chain, {
        "resume_context": format_resume_for_chat(resume.parsed, resume.raw_text),
        "analysis_context": analysis_context(user_id, resume.id),
        "history": hist,
        "message": message,
    })
    return (reply or "").strip()
