"""Unit tests for app.services.resume_parser_service.

Only the pure text-parsing helpers are tested here (no PDF I/O), so
these run instantly without needing a sample PDF file.
"""

from app.services.resume_parser_service import (
    extract_email,
    extract_github,
    extract_linkedin,
    extract_name,
    extract_phone,
    extract_skills,
)

SAMPLE_RESUME_TEXT = """John Smith
john.smith@example.com | +1 415-555-0134
linkedin.com/in/johnsmith | github.com/johnsmith

Skills
Python, JavaScript, SQL, Docker, Git

Experience
Software Engineer at Acme Corp
Built internal tooling used by 200+ engineers.

Education
B.Sc. Computer Science, State University
"""


def test_extract_email():
    assert extract_email(SAMPLE_RESUME_TEXT) == "john.smith@example.com"


def test_extract_phone():
    assert extract_phone(SAMPLE_RESUME_TEXT) != ""


def test_extract_linkedin():
    assert extract_linkedin(SAMPLE_RESUME_TEXT) == "linkedin.com/in/johnsmith"


def test_extract_github():
    assert extract_github(SAMPLE_RESUME_TEXT) == "github.com/johnsmith"


def test_extract_name():
    assert extract_name(SAMPLE_RESUME_TEXT) == "John Smith"


def test_extract_skills():
    skills = extract_skills(SAMPLE_RESUME_TEXT)
    assert "Python" in skills
    assert "Docker" in skills


def test_extract_email_missing_returns_empty_string():
    assert extract_email("No contact info here.") == ""
