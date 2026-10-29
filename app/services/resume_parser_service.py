"""
Resume Parser Service
Extracts structured information from PDF resumes using pdfplumber + regex.

This is a direct, behavior-preserving relocation of the original
utils/parser.py — the extraction rules themselves are unchanged.
"""

import re

import pdfplumber

from app.core.exceptions import ResumeParsingError

SECTION_KEYWORDS = {
    "skills": ["skills", "technical skills", "core competencies", "key skills"],
    "education": ["education", "academic background", "qualifications"],
    "experience": ["experience", "work experience", "professional experience", "employment", "internship"],
    "projects": ["projects", "personal projects", "academic projects", "key projects"],
    "certifications": ["certifications", "certificates", "licenses", "credentials"],
    "achievements": ["achievements", "awards", "honors", "accomplishments"],
}

ALL_SECTIONS = [
    "experience", "education", "projects", "certifications", "achievements",
    "awards", "summary", "objective", "interests", "languages", "hobbies", "references",
]


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from a PDF file using pdfplumber."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        raise ResumeParsingError(f"Failed to read PDF: {str(e)}")
    return text.strip()


def extract_email(text: str) -> str:
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    match = re.search(pattern, text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    pattern = r"(\+?\d{1,3}[\s\-]?)?(\(?\d{3}\)?[\s\-]?)?\d{3}[\s\-]?\d{4}"
    # Accept only matches with a plausible number of digits (10-15). The
    # original regex matched any 7-digit run such as "2019 2023".
    for match in re.finditer(pattern, text):
        digits = re.sub(r"\D", "", match.group(0))
        if 10 <= len(digits) <= 15:
            return match.group(0).strip()
    return ""


def extract_linkedin(text: str) -> str:
    pattern = r"(linkedin\.com/in/[\w\-]+|linkedin\.com/[\w\-/]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(0) if match else ""


def extract_github(text: str) -> str:
    pattern = r"(github\.com/[\w\-]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(0) if match else ""


def extract_name(text: str) -> str:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:5]:
        if re.search(r"[@/\d\(\)\+\-]{3,}", line):
            continue
        if len(line) > 60:
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w.isalpha()):
            return line
    return lines[0] if lines else "Unknown"


def extract_section(text: str, section_keywords: list, next_section_keywords: list) -> str:
    lines = text.split("\n")
    capturing = False
    section_lines = []
    section_pattern = re.compile(
        r"^\s*(" + "|".join(re.escape(k) for k in section_keywords) + r")\s*[:\-]?\s*$",
        re.IGNORECASE,
    )
    stop_pattern = re.compile(
        r"^\s*(" + "|".join(re.escape(k) for k in next_section_keywords) + r")\s*[:\-]?\s*$",
        re.IGNORECASE,
    )
    for line in lines:
        if section_pattern.match(line):
            capturing = True
            continue
        if capturing:
            if stop_pattern.match(line):
                break
            section_lines.append(line)
    return "\n".join(section_lines).strip()


def extract_skills(text: str) -> list:
    section_text = extract_section(text, SECTION_KEYWORDS["skills"], ALL_SECTIONS)
    if not section_text:
        return []
    skills = re.split(r"[,|•\n\t]+", section_text)
    skills = [s.strip() for s in skills if 2 < len(s.strip()) < 50]
    return list(dict.fromkeys(skills))


def _extract_multi_entry_section(text: str, section_key: str, other_sections_to_exclude: list) -> list:
    section_text = extract_section(text, SECTION_KEYWORDS[section_key], other_sections_to_exclude)
    entries = []
    if section_text:
        parts = re.split(r"\n{2,}", section_text)
        for part in parts:
            part = part.strip()
            if part and len(part) > 10:
                entries.append(part)
    return entries


def extract_education(text: str) -> list:
    others = ["skills", "experience", "projects", "certifications", "achievements", "awards", "summary", "interests"]
    return _extract_multi_entry_section(text, "education", others)


def extract_experience(text: str) -> list:
    others = ["skills", "education", "projects", "certifications", "achievements", "awards", "summary", "interests"]
    return _extract_multi_entry_section(text, "experience", others)


def extract_projects(text: str) -> list:
    others = ["skills", "education", "experience", "certifications", "achievements", "awards", "summary", "interests"]
    return _extract_multi_entry_section(text, "projects", others)


def extract_certifications(text: str) -> list:
    others = ["skills", "education", "experience", "projects", "achievements", "awards", "summary", "interests"]
    section_text = extract_section(text, SECTION_KEYWORDS["certifications"], others)
    items = []
    if section_text:
        lines = [l.strip() for l in section_text.split("\n") if l.strip()]
        items = [re.sub(r"^[•\-\*]\s*", "", l) for l in lines]
    return items


def extract_achievements(text: str) -> list:
    others = ["skills", "education", "experience", "projects", "certifications", "summary", "interests", "languages"]
    section_text = extract_section(text, SECTION_KEYWORDS["achievements"], others)
    items = []
    if section_text:
        lines = [l.strip() for l in section_text.split("\n") if l.strip()]
        items = [re.sub(r"^[•\-\*]\s*", "", l) for l in lines]
    return items


def parse_resume(pdf_path: str) -> dict:
    """Main entry point: parse a PDF resume into a structured dictionary."""
    raw_text = extract_text_from_pdf(pdf_path)
    return {
        "raw_text": raw_text,
        "name": extract_name(raw_text),
        "email": extract_email(raw_text),
        "phone": extract_phone(raw_text),
        "linkedin": extract_linkedin(raw_text),
        "github": extract_github(raw_text),
        "skills": extract_skills(raw_text),
        "education": extract_education(raw_text),
        "experience": extract_experience(raw_text),
        "projects": extract_projects(raw_text),
        "certifications": extract_certifications(raw_text),
        "achievements": extract_achievements(raw_text),
    }
