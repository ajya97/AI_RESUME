"""Resume template library — deterministic rendering only (no AI, no credits)."""

TEMPLATES = {
    "classic": {
        "name": "Classic", "description": "Traditional single-column layout with serif headings. Safe for every ATS.",
        "font": "Times-Roman", "font_bold": "Times-Bold", "accent": "#111111",
        "name_size": 20, "head_size": 12, "body_size": 10.5, "align": "center", "rule": True, "caps": True,
    },
    "modern": {
        "name": "Modern", "description": "Clean sans-serif with a blue accent colour. Single column, no graphics.",
        "font": "Helvetica", "font_bold": "Helvetica-Bold", "accent": "#1d4ed8",
        "name_size": 22, "head_size": 11.5, "body_size": 10, "align": "left", "rule": True, "caps": True,
    },
    "compact": {
        "name": "Compact", "description": "Tighter spacing to fit more on one page; ideal for experienced candidates.",
        "font": "Helvetica", "font_bold": "Helvetica-Bold", "accent": "#374151",
        "name_size": 18, "head_size": 10.5, "body_size": 9, "align": "left", "rule": False, "caps": True,
    },
    "minimal": {
        "name": "Minimal", "description": "Lots of white space and understated headings for a calm, readable page.",
        "font": "Helvetica", "font_bold": "Helvetica-Bold", "accent": "#6b7280",
        "name_size": 20, "head_size": 11, "body_size": 10, "align": "left", "rule": False, "caps": False,
    },
}

SECTION_ORDER = [
    ("summary", "Summary"), ("skills", "Skills"), ("experience", "Experience"), ("projects", "Projects"),
    ("education", "Education"), ("certifications", "Certifications"), ("achievements", "Achievements"),
]


def list_templates() -> list[dict]:
    return [{"key": k, "name": v["name"], "description": v["description"], "accent": v["accent"]}
            for k, v in TEMPLATES.items()]


def is_valid(key: str) -> bool:
    return key in TEMPLATES


def split_entry(entry: str) -> tuple[str, list[str]]:
    """First line = heading, remaining lines = bullet lines (leading bullets stripped)."""
    lines = [ln.strip() for ln in entry.splitlines() if ln.strip()]
    if not lines:
        return "", []
    bullets = [ln.lstrip("•-*· ").strip() for ln in lines[1:]]
    return lines[0], [b for b in bullets if b]


def contact_line(content: dict) -> list[str]:
    return [v for v in (content.get("email"), content.get("phone"), content.get("location"),
                        content.get("linkedin"), content.get("github")) if v]
