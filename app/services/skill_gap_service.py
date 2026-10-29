"""
Skill-gap analysis.

Deterministic part: skills the resume TEXT mentions (inferred — not verified by
any test) are compared with the skills the target role needs, taken from the
user-supplied job requirements when given, otherwise from the built-in role
catalogue (app/services/skill_catalog.py). The AI then turns the gap into a
prioritised learning plan and project ideas.
"""

from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser

from app.core.exceptions import ValidationError
from app.prompts.career_prompts import skill_gap_prompt
from app.prompts.formatting import format_full_resume_summary
from app.schemas.career_schema import SkillGapPlan
from app.services.ai_parsing import parse_model_output
from app.services.llm_client import get_chat_model, invoke_chain
from app.services.skill_catalog import extract_skills, match_role

VERIFIED_NOTE = ("Skills are inferred from words in your resume. They have not been verified by any "
                 "assessment or test.")


def clean_target_role(role) -> str:
    if not isinstance(role, str) or len(role.strip()) < 2:
        raise ValidationError("Please enter a target job role.")
    role = role.strip()
    if len(role) > 120:
        raise ValidationError("Target role is too long (max 120 characters).")
    return role


def compute_gap(target_role: str, requirements: str, resume_text: str, resume_skills: list[str]) -> dict:
    current = extract_skills((resume_text or "") + "\n" + "\n".join(resume_skills or []))
    catalogue_role, role_skills = match_role(target_role)
    if requirements.strip():
        required = list(extract_skills(requirements).keys())
        source = "job requirements you provided"
    else:
        required = role_skills
        source = f"built-in skill list for “{catalogue_role}”" if catalogue_role else ""
    if not required:
        raise ValidationError(
            "We couldn't determine the skills for that role. Paste the job requirements or "
            "choose a more common role title (e.g. Data Analyst, Backend Developer).",
            code="role_unknown")
    matched = [s for s in required if s in current]
    missing = [s for s in required if s not in current]
    coverage = round(len(matched) / len(required) * 100)
    return {
        "role_source": source,
        "catalogue_role": catalogue_role,
        "required_skills": required,
        "current_skills": sorted(current.keys()),
        "matched_skills": matched,
        "missing_skills": missing,
        "coverage_percent": coverage,
        "verification_note": VERIFIED_NOTE,
    }


def learning_plan(parsed: dict, target_role: str, requirements: str, gap: dict) -> dict:
    llm = get_chat_model(temperature=0.5, max_tokens=2500)
    parser = PydanticOutputParser(pydantic_object=SkillGapPlan)
    chain = skill_gap_prompt | llm | StrOutputParser()
    raw = invoke_chain(chain, {
        "target_role": target_role,
        "resume_summary": format_full_resume_summary(parsed),
        "requirements": (requirements or "(none provided; role catalogue used)")[:8000],
        "current_skills": ", ".join(gap["current_skills"][:60]) or "none detected",
        "missing_skills": ", ".join(gap["missing_skills"]) or "none",
        "format_instructions": parser.get_format_instructions(),
    })
    plan = parse_model_output(raw, SkillGapPlan)
    for item in plan["learning_plan"]:
        item["status"] = "todo"  # self-reported progress tracking
    return plan
