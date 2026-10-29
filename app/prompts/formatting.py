"""Helpers to render parsed resume dicts into plain-text summaries used
inside prompt templates."""


def format_full_resume_summary(parsed: dict) -> str:
    """Full resume summary used by the deep-analysis chain."""
    return f"""
Name: {parsed.get('name', 'N/A')}
Email: {parsed.get('email', 'N/A')}
Phone: {parsed.get('phone', 'N/A')}
LinkedIn: {parsed.get('linkedin', 'N/A')}
GitHub: {parsed.get('github', 'N/A')}

Skills: {', '.join(parsed.get('skills', []))}

Education:
{chr(10).join(parsed.get('education', []))}

Experience:
{chr(10).join(parsed.get('experience', []))}

Projects:
{chr(10).join(parsed.get('projects', []))}

Certifications:
{', '.join(parsed.get('certifications', []))}

Achievements:
{', '.join(parsed.get('achievements', []))}
""".strip()


def format_interview_resume_summary(parsed: dict) -> str:
    """Trimmed resume summary used by the interview-question chain."""
    return f"""
Name: {parsed.get('name', 'Candidate')}
Skills: {', '.join(parsed.get('skills', [])[:15])}
Experience: {chr(10).join(parsed.get('experience', [])[:3])}
Projects: {chr(10).join(parsed.get('projects', [])[:3])}
Education: {chr(10).join(parsed.get('education', [])[:2])}
Certifications: {', '.join(parsed.get('certifications', [])[:5])}
""".strip()


def format_candidate_context(parsed_resume: dict) -> str:
    """Trimmed candidate context used by the answer-evaluation chain."""
    return f"""
Skills: {', '.join(parsed_resume.get('skills', [])[:10])}
Experience snippets: {' | '.join(parsed_resume.get('experience', [])[:2])}
Projects: {' | '.join(parsed_resume.get('projects', [])[:2])}
""".strip()


def format_resume_for_chat(parsed: dict, raw_text: str, limit: int = 12000) -> str:
    """Resume context for the chatbot: raw text (truncated) is the source of truth."""
    text = (raw_text or "").strip()
    if len(text) > limit:
        text = text[:limit] + "\n[...truncated...]"
    return text or format_full_resume_summary(parsed)
