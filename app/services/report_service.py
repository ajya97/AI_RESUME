"""Orchestrates billable analyses: each runs inside ``billable`` so a failure at
ANY step (provider, parsing, database) refunds the credits."""

from app.extensions import db
from app.models.resume import Report
from app.services import job_match_service, skill_gap_service
from app.services.ats_score_service import calculate_ats_score, detect_errors, detect_missing_sections
from app.services.credit_service import billable
from app.services.resume_analysis_service import analyze_resume_with_gpt

ATS_NOTE = ("This is a heuristic ATS-compatibility score from this app's own rules. It is not the output of "
            "any employer's applicant tracking system, which use proprietary and differing criteria.")


def _full_parsed(resume) -> dict:
    parsed = dict(resume.parsed or {})
    parsed["raw_text"] = resume.raw_text
    return parsed


def run_ats_analysis(user, resume, idempotency_key=None) -> Report:
    parsed = _full_parsed(resume)
    with billable(user.id, "ats_analysis", idempotency_key=idempotency_key,
                  description=f"ATS analysis: {resume.original_filename}") as tx:
        ats = calculate_ats_score(parsed)
        missing = detect_missing_sections(parsed)
        errors = detect_errors(parsed)
        gpt = analyze_resume_with_gpt(parsed)  # may raise -> refund
        data = {
            "parsed": resume.parsed, "ats": ats, "missing_sections": missing, "errors": errors,
            "gpt_analysis": gpt, "ats_note": ATS_NOTE,
        }
        report = Report(user_id=user.id, resume_id=resume.id, type="ats",
                        title=f"ATS analysis — {resume.original_filename}",
                        score=ats["total_score"], inputs={}, data=data, credit_tx_id=tx.id)
        db.session.add(report)
        db.session.commit()
    return report


def run_job_match(user, resume, jd_text: str, idempotency_key=None) -> Report:
    comparison = job_match_service.compute_match(jd_text, resume.raw_text, (resume.parsed or {}).get("skills"))
    with billable(user.id, "job_match", idempotency_key=idempotency_key,
                  description=f"Job match: {resume.original_filename}") as tx:
        advice = job_match_service.job_match_advice(_full_parsed(resume), jd_text, comparison)
        first = next((ln.strip() for ln in jd_text.splitlines() if ln.strip()), "Job description")[:80]
        report = Report(user_id=user.id, resume_id=resume.id, type="job_match",
                        title=f"Job match — {first}", score=comparison["score"],
                        inputs={"job_description": jd_text}, data={"comparison": comparison, "advice": advice},
                        credit_tx_id=tx.id)
        db.session.add(report)
        db.session.commit()
    return report


def run_skill_gap(user, resume, target_role: str, requirements: str, idempotency_key=None) -> Report:
    gap = skill_gap_service.compute_gap(target_role, requirements, resume.raw_text, (resume.parsed or {}).get("skills"))
    with billable(user.id, "skill_gap", idempotency_key=idempotency_key,
                  description=f"Skill gap: {target_role}") as tx:
        plan = skill_gap_service.learning_plan(_full_parsed(resume), target_role, requirements, gap)
        report = Report(user_id=user.id, resume_id=resume.id, type="skill_gap",
                        title=f"Skill gap — {target_role}", score=gap["coverage_percent"],
                        inputs={"target_role": target_role, "requirements": requirements},
                        data={"gap": gap, "plan": plan}, credit_tx_id=tx.id)
        db.session.add(report)
        db.session.commit()
    return report
