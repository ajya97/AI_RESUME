"""Unit tests for app.services.ats_score_service.

These are pure functions (no LLM/network calls), so they run instantly
and deterministically.
"""

from app.services.ats_score_service import (
    calculate_ats_score,
    detect_errors,
    detect_missing_sections,
)

FULL_PARSED = {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "9876543210",
    "linkedin": "linkedin.com/in/janedoe",
    "github": "github.com/janedoe",
    "skills": ["Python", "SQL", "Docker", "Git", "React", "AWS", "Java", "JavaScript", "Flask", "Pandas", "NumPy"],
    "education": ["Bachelor of Technology, CGPA 8.5"],
    "experience": [
        "Developed and led a team of 5 engineers, improved API latency by 40%",
    ],
    "projects": [
        "Built a resume analyzer, deployed on GitHub with a live demo",
    ],
    "certifications": ["AWS Certified Developer", "Google Data Analytics", "Coursera ML"],
    "achievements": ["Won hackathon"],
    "raw_text": (
        "Jane Doe\nSummary\nExperienced developer.\n\n"
        "Technical Skills\nPython, SQL\n\n"
        "Developed and led a team of 5 engineers, improved API latency by 40%\n"
    ),
}

EMPTY_PARSED = {
    "name": "Unknown",
    "email": "",
    "phone": "",
    "linkedin": "",
    "github": "",
    "skills": [],
    "education": [],
    "experience": [],
    "projects": [],
    "certifications": [],
    "achievements": [],
    "raw_text": "Just a name\nNo real sections here.",
}


def test_calculate_ats_score_full_resume_scores_high():
    result = calculate_ats_score(FULL_PARSED)
    assert result["max_score"] == 100
    assert result["total_score"] > 60
    assert result["rating"] in {"Good", "Excellent"}
    assert "contact_info" in result["sections"]


def test_calculate_ats_score_empty_resume_scores_low():
    result = calculate_ats_score(EMPTY_PARSED)
    assert result["total_score"] < 30
    assert result["rating"] in {"Poor", "Below Average"}


def test_detect_missing_sections_flags_everything_for_empty_resume():
    missing = detect_missing_sections(EMPTY_PARSED)
    missing_names = {m["section"] for m in missing}
    assert "Contact Email" in missing_names
    assert "Skills Section" in missing_names
    assert "Projects" in missing_names


def test_detect_missing_sections_flags_nothing_for_full_resume():
    missing = detect_missing_sections(FULL_PARSED)
    assert missing == []


def test_detect_errors_flags_critical_missing_contact_info():
    errors = detect_errors(EMPTY_PARSED)
    error_types = {e["type"] for e in errors}
    assert "Missing Email" in error_types
    assert "Missing Phone Number" in error_types


def test_detect_errors_no_critical_errors_for_full_resume():
    errors = detect_errors(FULL_PARSED)
    critical = [e for e in errors if e["severity"] == "Critical"]
    assert critical == []
