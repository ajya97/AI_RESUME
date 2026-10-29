"""
ATS Score Service
Calculates an ATS score (0-100) based on resume completeness and quality,
plus missing-section and common-error detection.

Direct, behavior-preserving relocation of the original utils/ats_score.py.
"""

import re

STRONG_ACTION_VERBS = [
    "achieved", "built", "created", "delivered", "designed", "developed", "engineered",
    "established", "executed", "generated", "implemented", "improved", "increased",
    "launched", "led", "managed", "optimized", "produced", "reduced", "solved", "spearheaded",
]

WEAK_WORDS = [
    "responsible for", "assisted with", "helped with", "worked on", "involved in",
    "participated in", "was part of", "tried to",
]

ATS_KEYWORDS_BY_ROLE = {
    "data_analyst": [
        "sql", "python", "tableau", "power bi", "excel", "data visualization",
        "statistical analysis", "machine learning", "pandas", "numpy",
    ],
    "ai_engineer": [
        "tensorflow", "pytorch", "deep learning", "nlp", "computer vision",
        "neural networks", "transformers", "hugging face", "langchain", "llm",
    ],
    "python_developer": [
        "django", "flask", "fastapi", "rest api", "postgresql", "docker",
        "git", "unit testing", "celery", "redis",
    ],
    "full_stack": [
        "react", "node.js", "html", "css", "javascript", "mongodb", "postgresql",
        "rest api", "docker", "git", "ci/cd",
    ],
}


def score_contact_info(parsed: dict) -> dict:
    score = 0
    breakdown = {}

    if parsed.get("email"):
        score += 3
        breakdown["email"] = {"points": 3, "status": "present"}
    else:
        breakdown["email"] = {"points": 0, "status": "missing", "tip": "Add your email address"}

    if parsed.get("phone"):
        score += 3
        breakdown["phone"] = {"points": 3, "status": "present"}
    else:
        breakdown["phone"] = {"points": 0, "status": "missing", "tip": "Add a phone number"}

    if parsed.get("linkedin"):
        score += 2
        breakdown["linkedin"] = {"points": 2, "status": "present"}
    else:
        breakdown["linkedin"] = {"points": 0, "status": "missing", "tip": "Add your LinkedIn profile URL"}

    if parsed.get("github"):
        score += 2
        breakdown["github"] = {"points": 2, "status": "present"}
    else:
        breakdown["github"] = {"points": 0, "status": "missing", "tip": "Add your GitHub profile URL"}

    return {"score": score, "max": 10, "breakdown": breakdown}


def score_skills_section(parsed: dict) -> dict:
    skills = parsed.get("skills", [])
    score = 0
    tips = []

    if len(skills) >= 10:
        score += 10
    elif len(skills) >= 5:
        score += 6
        tips.append("Add more skills (aim for 10+)")
    elif len(skills) > 0:
        score += 3
        tips.append("Skills section is sparse — add more relevant skills")
    else:
        tips.append("No skills section detected — this is critical for ATS")

    raw_text = parsed.get("raw_text", "")
    if re.search(r"(technical|programming|tools|frameworks|soft skills)", raw_text, re.IGNORECASE):
        score += 5
    else:
        tips.append("Categorize skills (e.g., Technical Skills, Tools, Languages)")

    skills_text = " ".join(skills).lower()
    tech_hits = sum(1 for kw in ["python", "javascript", "sql", "git", "docker", "aws", "react", "java"] if kw in skills_text)
    score += min(tech_hits, 5)

    return {"score": min(score, 20), "max": 20, "tips": tips}


def score_experience(parsed: dict) -> dict:
    experience = parsed.get("experience", [])
    score = 0
    tips = []

    if len(experience) >= 3:
        score += 10
    elif len(experience) >= 1:
        score += 6
        tips.append("Add more experience entries or internships")
    else:
        tips.append("No experience section — add internships, part-time work, or freelance projects")

    exp_text = " ".join(experience).lower()
    verb_hits = sum(1 for v in STRONG_ACTION_VERBS if v in exp_text)
    if verb_hits >= 5:
        score += 6
    elif verb_hits >= 2:
        score += 3
        tips.append("Use more strong action verbs (e.g., 'Developed', 'Optimized', 'Led')")
    else:
        tips.append("Avoid weak phrases — use strong action verbs to start each bullet")

    if re.search(r"\d+[\%\+x]|\d+ (users|projects|clients|features)", exp_text):
        score += 4
    else:
        tips.append("Quantify achievements (e.g., 'Increased performance by 40%')")

    weak_found = [w for w in WEAK_WORDS if w in exp_text]
    if weak_found:
        tips.append(f"Avoid weak phrases: {', '.join(weak_found[:3])}")

    return {"score": min(score, 20), "max": 20, "tips": tips}


def score_education(parsed: dict) -> dict:
    education = parsed.get("education", [])
    score = 0
    tips = []

    if len(education) >= 1:
        score += 10
        edu_text = " ".join(education).lower()
        if re.search(r"(gpa|cgpa|\d\.\d{1,2})", edu_text):
            score += 3
        else:
            tips.append("Include your GPA/CGPA if it's 7.0+")
        if re.search(r"(bachelor|master|b\.tech|m\.tech|b\.e|b\.sc|m\.sc|phd)", edu_text):
            score += 2
    else:
        tips.append("No education section found — this is mandatory")

    return {"score": min(score, 15), "max": 15, "tips": tips}


def score_projects(parsed: dict) -> dict:
    projects = parsed.get("projects", [])
    score = 0
    tips = []

    if len(projects) >= 3:
        score += 10
    elif len(projects) >= 1:
        score += 6
        tips.append("Add more projects (aim for 3+ for a strong profile)")
    else:
        tips.append("No projects section — for FYP/entry-level, projects are critical")

    proj_text = " ".join(projects).lower()
    if re.search(r"(github|live|deployed|hosted|demo)", proj_text):
        score += 3
    else:
        tips.append("Add GitHub links or live demo URLs to your projects")

    if re.search(r"(built|developed|designed|implemented)", proj_text):
        score += 2
    else:
        tips.append("Describe what you built and the tech stack used")

    return {"score": min(score, 15), "max": 15, "tips": tips}


def score_certifications(parsed: dict) -> dict:
    certs = parsed.get("certifications", [])
    score = 0
    tips = []

    if len(certs) >= 3:
        score += 10
    elif len(certs) >= 1:
        score += 6
        tips.append("Get more certifications from Coursera, Google, or AWS")
    else:
        tips.append("No certifications found — add relevant online certificates to boost ATS score")

    return {"score": min(score, 10), "max": 10, "tips": tips}


def score_keyword_density(parsed: dict) -> dict:
    raw_text = parsed.get("raw_text", "").lower()
    total_keywords = []
    for role_kws in ATS_KEYWORDS_BY_ROLE.values():
        total_keywords.extend(role_kws)
    unique_kws = list(set(total_keywords))
    hits = sum(1 for kw in unique_kws if kw in raw_text)
    ratio = hits / len(unique_kws) if unique_kws else 0

    score = min(int(ratio * 10 * 3), 10)
    tips = []
    if score < 5:
        tips.append("Use more industry-specific keywords relevant to your target role")
    if score < 8:
        tips.append("Mirror keywords from job descriptions you're targeting")

    return {"score": score, "max": 10, "tips": tips, "keyword_hits": hits}


def calculate_ats_score(parsed: dict) -> dict:
    """Main ATS scoring function. Returns total score, per-section
    breakdown, and improvement tips."""
    contact = score_contact_info(parsed)
    skills = score_skills_section(parsed)
    experience = score_experience(parsed)
    education = score_education(parsed)
    projects = score_projects(parsed)
    certs = score_certifications(parsed)
    keywords = score_keyword_density(parsed)

    total = (
        contact["score"] + skills["score"] + experience["score"]
        + education["score"] + projects["score"] + certs["score"] + keywords["score"]
    )

    all_tips = []
    all_tips.extend(skills.get("tips", []))
    all_tips.extend(experience.get("tips", []))
    all_tips.extend(education.get("tips", []))
    all_tips.extend(projects.get("tips", []))
    all_tips.extend(certs.get("tips", []))
    all_tips.extend(keywords.get("tips", []))

    if total >= 85:
        rating = "Excellent"
    elif total >= 70:
        rating = "Good"
    elif total >= 55:
        rating = "Average"
    elif total >= 40:
        rating = "Below Average"
    else:
        rating = "Poor"

    return {
        "total_score": total,
        "max_score": 100,
        "rating": rating,
        "sections": {
            "contact_info": contact,
            "skills": skills,
            "experience": experience,
            "education": education,
            "projects": projects,
            "certifications": certs,
            "keyword_density": keywords,
        },
        "top_tips": all_tips[:8],
    }


def detect_missing_sections(parsed: dict) -> list:
    """Detect which important resume sections are missing."""
    missing = []
    checks = [
        {"key": "email", "section": "Contact Email",
         "why": "ATS systems and recruiters need your email to contact you.",
         "suggestion": "Add a professional email address at the top of your resume."},
        {"key": "phone", "section": "Phone Number",
         "why": "Recruiters prefer phone calls for quick screening.",
         "suggestion": "Add your phone number in international format."},
        {"key": "linkedin", "section": "LinkedIn Profile",
         "why": "85% of recruiters check LinkedIn before calling candidates.",
         "suggestion": "Add your LinkedIn URL: linkedin.com/in/yourname"},
        {"key": "github", "section": "GitHub Profile",
         "why": "For tech roles, GitHub is your live portfolio.",
         "suggestion": "Add your GitHub URL: github.com/yourusername"},
        {"key": "skills", "section": "Skills Section",
         "why": "ATS systems scan skills keywords to match job descriptions.",
         "suggestion": "Add a dedicated Skills section with technical and soft skills."},
        {"key": "experience", "section": "Work Experience",
         "why": "Experience is the #1 factor recruiters look at.",
         "suggestion": "Add internships, part-time jobs, or freelance work."},
        {"key": "projects", "section": "Projects",
         "why": "Projects demonstrate real-world application of skills.",
         "suggestion": "Add 2-4 projects with descriptions, tech stack, and GitHub links."},
        {"key": "certifications", "section": "Certifications",
         "why": "Certifications validate your skills and boost ATS ranking.",
         "suggestion": "Add certifications from Google, AWS, Coursera, or Udemy."},
        {"key": "achievements", "section": "Achievements / Awards",
         "why": "Shows you go beyond the minimum — differentiates you from others.",
         "suggestion": "Add hackathon wins, scholarships, rank, or special recognitions."},
    ]

    for check in checks:
        value = parsed.get(check["key"])
        if not value or (isinstance(value, list) and len(value) == 0):
            missing.append({
                "section": check["section"],
                "why_it_matters": check["why"],
                "suggestion": check["suggestion"],
            })

    return missing


def detect_errors(parsed: dict) -> list:
    """Detect common resume errors and return with severity levels."""
    errors = []
    raw_text = parsed.get("raw_text", "")

    if not parsed.get("email"):
        errors.append({"type": "Missing Email", "severity": "Critical", "fix": "Add your email address to the top of the resume."})
    if not parsed.get("phone"):
        errors.append({"type": "Missing Phone Number", "severity": "Critical", "fix": "Add your phone number in international format."})
    if not parsed.get("linkedin"):
        errors.append({"type": "Missing LinkedIn", "severity": "High", "fix": "Add your LinkedIn profile URL."})
    if not parsed.get("github"):
        errors.append({"type": "Missing GitHub", "severity": "High", "fix": "Add your GitHub profile URL."})

    if not parsed.get("projects"):
        errors.append({"type": "No Projects Section", "severity": "High", "fix": "Add a Projects section with 2-4 relevant projects."})
    if not parsed.get("certifications"):
        errors.append({"type": "No Certifications", "severity": "Medium", "fix": "Add relevant certifications to strengthen your profile."})

    exp_text = " ".join(parsed.get("experience", [])).lower()
    weak_found = [w for w in WEAK_WORDS if w in exp_text]
    if weak_found:
        errors.append({
            "type": "Weak Action Verbs",
            "severity": "High",
            "fix": f"Replace phrases like '{weak_found[0]}' with strong verbs: Developed, Led, Built, Achieved.",
        })

    paragraphs = [p for p in raw_text.split("\n\n") if len(p.split()) > 60]
    if paragraphs:
        errors.append({"type": "Long Paragraphs", "severity": "Medium", "fix": "Break long paragraphs into bullet points (max 2-3 lines each)."})

    if not re.search(r"\d+[\%\+x]|\d+ (users|projects|clients|features|teams|members)", exp_text):
        errors.append({"type": "No Quantified Results", "severity": "Medium", "fix": "Add numbers to achievements (e.g., 'Improved speed by 30%', 'Managed team of 5')."})

    if not re.search(r"(summary|objective|profile|about)", raw_text, re.IGNORECASE):
        errors.append({"type": "Missing Professional Summary", "severity": "Medium", "fix": "Add a 3-4 line professional summary at the top of your resume."})

    return errors
