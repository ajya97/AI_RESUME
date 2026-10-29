"""
Job-description matching.

METHODOLOGY (deterministic part — documented in the README and shown in the UI)
------------------------------------------------------------------------------
1. Skills are detected with a fixed vocabulary (app/services/skill_catalog.py)
   in both the job description and the resume. Skills in a "required /
   qualifications / must have" part of the JD weigh 2, skills in a
   "preferred / nice to have / bonus" part weigh 1 (default: required).
2. skill_score    = weight of JD skills found in the resume / total JD weight.
3. keyword_score  = share of the JD's top-30 distinctive words found in the resume.
4. experience_score = min(estimated resume years / years requested by the JD, 1)
   (only if the JD states a number of years; resume years are an ESTIMATE from
   date ranges).
5. match_score = weighted mean of the available components
   (skills 60 %, keywords 25 %, experience 15 %, re-normalised if a component
   is unavailable).

The score is a transparent heuristic, NOT a prediction of hiring outcomes or of
any employer's ATS. AI advice (summary, requirement comparison, tailored
suggestions) is generated afterwards from this comparison.
"""

import re
from collections import Counter
from datetime import date

from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser

from app.core.exceptions import ValidationError
from app.prompts.career_prompts import job_match_prompt
from app.prompts.formatting import format_full_resume_summary
from app.schemas.career_schema import JobMatchAdvice
from app.services.ai_parsing import parse_model_output
from app.services.llm_client import get_chat_model, invoke_chain
from app.services.skill_catalog import extract_skills

STOPWORDS = set("""a about above after again all also an and any are as at be because been before being below between both
but by can could did do does doing down during each few for from further had has have having he her here hers him his how i if
in into is it its itself just me more most my no nor not now of off on once only or other our ours out over own same she should
so some such than that the their theirs them then there these they this those through to too under until up very was we were
what when where which while who whom why will with would you your yours job role position candidate candidates work working
experience years year team teams ability strong good great excellent skills skill knowledge understanding proficiency including
etc plus well must required requirements preferred responsibilities qualifications looking join company business using use used
new
across develop development developing support environment related""".split())

REQ_HEAD = re.compile(r"(requirement|required|must[- ]have|qualification|what you.?ll need|what we.?re looking|minimum)", re.I)
PREF_HEAD = re.compile(r"(preferred|nice[- ]to[- ]have|bonus|good to have|a plus|desirable|optional)", re.I)
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)\b", re.I)
RANGE = re.compile(r"\b((?:19|20)\d{2})\s*(?:-|–|—|to)\s*((?:19|20)\d{2}|present|current|now|ongoing)\b", re.I)


def clean_job_description(text) -> str:
    if not isinstance(text, str):
        raise ValidationError("Job description is required.")
    text = text.strip()
    if len(text) < 40:
        raise ValidationError("Please paste a longer job description (at least 40 characters).")
    return text


def jd_skill_weights(jd_text: str) -> dict[str, int]:
    """{skill: weight} — required=2, preferred=1."""
    weights: dict[str, int] = {}
    mode = 2
    for line in jd_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        short = len(stripped) < 70
        if short and PREF_HEAD.search(stripped):
            mode = 1
        elif short and REQ_HEAD.search(stripped):
            mode = 2
        line_mode = 1 if (PREF_HEAD.search(stripped) and not short) else mode
        for skill in extract_skills(stripped):
            weights[skill] = max(weights.get(skill, 0), line_mode)
    return weights


def jd_keywords(jd_text: str, top: int = 30) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z+#.\-]{2,}", jd_text.lower())
    counts = Counter(w.strip(".-") for w in words if w.strip(".-") not in STOPWORDS and len(w.strip(".-")) > 2)
    return [w for w, _ in counts.most_common(top)]


def estimate_resume_years(raw_text: str) -> float:
    """Estimate years of experience from merged year ranges (heuristic)."""
    now = date.today().year
    spans = []
    for a, b in RANGE.findall(raw_text or ""):
        start = int(a)
        end = now if not b.isdigit() else int(b)
        if 1970 <= start <= end <= now + 1 and end - start <= 40:
            spans.append((start, end))
    spans.sort()
    total, cur_s, cur_e = 0, None, None
    for s, e in spans:
        if cur_s is None:
            cur_s, cur_e = s, e
        elif s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
    if cur_s is not None:
        total += cur_e - cur_s
    return float(total)


def jd_required_years(jd_text: str) -> int | None:
    vals = [int(m.group(1)) for m in YEARS.finditer(jd_text) if 0 < int(m.group(1)) <= 25]
    return max(vals) if vals else None


def compute_match(jd_text: str, resume_text: str, resume_skills: list[str] | None = None) -> dict:
    jd_w = jd_skill_weights(jd_text)
    resume_blob = (resume_text or "") + "\n" + "\n".join(resume_skills or [])
    resume_found = extract_skills(resume_blob)
    jd_counts = extract_skills(jd_text)

    matched = sorted(s for s in jd_w if s in resume_found)
    missing_required = sorted(s for s, w in jd_w.items() if w == 2 and s not in resume_found)
    missing_preferred = sorted(s for s, w in jd_w.items() if w == 1 and s not in resume_found)
    underrep = sorted(s for s in matched if resume_found.get(s, 0) <= 1 and jd_counts.get(s, 0) >= 2)

    total_w = sum(jd_w.values())
    skill_score = (sum(w for s, w in jd_w.items() if s in resume_found) / total_w * 100) if total_w else None

    keywords = jd_keywords(jd_text)
    resume_tokens = set(re.findall(r"[a-zA-Z][a-zA-Z+#.\-]{2,}", resume_blob.lower()))
    resume_tokens = {t.strip(".-") for t in resume_tokens}
    kw_hit = [k for k in keywords if k in resume_tokens]
    kw_miss = [k for k in keywords if k not in resume_tokens]
    keyword_score = (len(kw_hit) / len(keywords) * 100) if keywords else None

    req_years = jd_required_years(jd_text)
    res_years = estimate_resume_years(resume_text)
    exp_score = min(res_years / req_years, 1) * 100 if req_years else None

    parts = [(skill_score, 0.60), (keyword_score, 0.25), (exp_score, 0.15)]
    avail = [(v, w) for v, w in parts if v is not None]
    score = round(sum(v * w for v, w in avail) / sum(w for _, w in avail)) if avail else 0

    return {
        "score": int(score),
        "components": {
            "skills": None if skill_score is None else round(skill_score),
            "keywords": None if keyword_score is None else round(keyword_score),
            "experience": None if exp_score is None else round(exp_score),
        },
        "matched_skills": matched,
        "missing_required_skills": missing_required,
        "missing_preferred_skills": missing_preferred,
        "underrepresented_skills": underrep,
        "keyword_coverage": {"percent": None if keyword_score is None else round(keyword_score),
                             "found": kw_hit, "missing": kw_miss},
        "experience": {"required_years": req_years, "estimated_resume_years": res_years,
                       "note": "Resume years are estimated from date ranges and may be inaccurate."},
        "methodology": ("Heuristic: 60% skills (required skills weigh double), 25% keyword coverage, "
                        "15% experience years (when the job states them). Not an employer ATS score "
                        "and not a hiring prediction."),
    }


def job_match_advice(parsed: dict, jd_text: str, comparison: dict) -> dict:
    llm = get_chat_model(temperature=0.4, max_tokens=2000)
    parser = PydanticOutputParser(pydantic_object=JobMatchAdvice)
    chain = job_match_prompt | llm | StrOutputParser()
    j = lambda xs: ", ".join(xs) or "none"  # noqa: E731
    raw = invoke_chain(chain, {
        "job_description": jd_text[:8000],
        "resume_summary": format_full_resume_summary(parsed),
        "matched": j(comparison["matched_skills"]),
        "missing_required": j(comparison["missing_required_skills"]),
        "missing_preferred": j(comparison["missing_preferred_skills"]),
        "underrepresented": j(comparison["underrepresented_skills"]),
        "format_instructions": parser.get_format_instructions(),
    })
    return parse_model_output(raw, JobMatchAdvice)
