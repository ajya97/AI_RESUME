"""
Deterministic skill vocabulary used by job matching and skill-gap analysis.

``extract_skills(text)`` returns canonical skill names found in free text using
whole-word, case-insensitive matching with aliases. It is a transparent,
reproducible heuristic: it only knows the skills listed here.
"""

import re
from functools import lru_cache

# canonical name -> aliases (the canonical name itself is always matched)
SKILLS: dict[str, list[str]] = {
    # languages
    "Python": [], "Java": [], "JavaScript": ["js", "ecmascript", "es6"], "TypeScript": ["ts"],
    "C++": ["cpp"], "C#": ["csharp"], "Go": ["golang", "go programming", "go language"], "Rust": [], "Ruby": [], "PHP": [], "Kotlin": [],
    "Swift": [], "Scala": [], "R": ["r programming", "r language"], "MATLAB": [], "Bash": ["shell scripting"],
    "SQL": [], "HTML": ["html5"], "CSS": ["css3"],
    # web
    "React": ["react.js", "reactjs"], "Angular": ["angularjs"], "Vue": ["vue.js", "vuejs"], "Next.js": ["nextjs"],
    "Node.js": ["nodejs", "node"], "Express": ["express.js", "expressjs"], "Django": [], "Flask": [],
    "FastAPI": [], "Spring Boot": ["spring framework"], ".NET": ["dotnet", "asp.net"], "Tailwind CSS": ["tailwind"],
    "Bootstrap": [], "REST API": ["rest apis", "restful", "restful api", "restful apis"], "GraphQL": [],
    "Microservices": ["microservice"], "WebSockets": ["websocket"],
    # data / ml
    "Pandas": [], "NumPy": [], "scikit-learn": ["sklearn", "scikit learn"], "TensorFlow": [], "PyTorch": [],
    "Keras": [], "Machine Learning": ["ml"], "Deep Learning": [], "NLP": ["natural language processing"],
    "Computer Vision": [], "LLM": ["llms", "large language models", "large language model"],
    "LangChain": [], "Hugging Face": ["huggingface"], "Transformers": [], "Data Visualization": ["data visualisation"],
    "Statistics": ["statistical analysis"], "Tableau": [], "Power BI": ["powerbi"], "Excel": ["ms excel", "microsoft excel"],
    "Spark": ["pyspark", "apache spark"], "Hadoop": [], "Airflow": ["apache airflow"], "ETL": [],
    "Data Analysis": ["data analytics"], "A/B Testing": ["ab testing", "a/b test"], "OpenCV": [],
    "Neural Networks": ["neural network"], "RAG": ["retrieval augmented generation", "retrieval-augmented generation"],
    "Prompt Engineering": [],
    # databases
    "PostgreSQL": ["postgres"], "MySQL": [], "MongoDB": [], "Redis": [], "SQLite": [], "Oracle": [],
    "Elasticsearch": [], "DynamoDB": [], "Cassandra": [], "SQLAlchemy": [], "NoSQL": [],
    # cloud / devops
    "AWS": ["amazon web services"], "Azure": [], "GCP": ["google cloud", "google cloud platform"],
    "Docker": [], "Kubernetes": ["k8s"], "Terraform": [], "Ansible": [], "Jenkins": [],
    "CI/CD": ["ci cd", "continuous integration", "continuous delivery", "continuous deployment"],
    "GitHub Actions": [], "Linux": [], "Git": [], "GitHub": [], "Nginx": [], "Celery": [], "Kafka": ["apache kafka"],
    "RabbitMQ": [], "Prometheus": [], "Grafana": [], "Serverless": [],
    # testing / practices
    "Unit Testing": ["unit tests", "pytest", "unittest", "jest", "junit"], "TDD": ["test driven development", "test-driven development"],
    "Agile": ["scrum"], "Jira": [], "Selenium": [], "Playwright": [], "Cypress": [], "System Design": [],
    "Data Structures": ["data structures and algorithms", "dsa"], "Algorithms": [], "OOP": ["object oriented programming", "object-oriented programming", "object oriented"],
    # mobile
    "Android": [], "iOS": [], "React Native": [], "Flutter": [],
    # security
    "Cybersecurity": ["information security", "infosec"], "OAuth": ["oauth2"], "Penetration Testing": ["pentesting"],
    # soft / professional
    "Communication": [], "Leadership": [], "Problem Solving": ["problem-solving"], "Teamwork": ["collaboration"],
    "Project Management": [], "Stakeholder Management": [], "Mentoring": [],
    # design / product
    "Figma": [], "UI/UX": ["ux design", "ui design", "user experience"], "Product Management": [],
}

ROLE_SKILLS: dict[str, dict] = {
    "Data Analyst": {"match": ["data analyst", "business analyst", "analytics"],
                     "skills": ["SQL", "Python", "Excel", "Tableau", "Power BI", "Statistics", "Data Visualization",
                                "Pandas", "Data Analysis", "A/B Testing", "Communication"]},
    "Data Scientist": {"match": ["data scientist", "data science"],
                       "skills": ["Python", "SQL", "Machine Learning", "Statistics", "Pandas", "NumPy", "scikit-learn",
                                  "Deep Learning", "Data Visualization", "A/B Testing", "Spark"]},
    "Machine Learning / AI Engineer": {"match": ["machine learning", "ml engineer", "ai engineer", "artificial intelligence", "llm"],
                                       "skills": ["Python", "PyTorch", "TensorFlow", "Machine Learning", "Deep Learning", "NLP",
                                                  "LLM", "LangChain", "Docker", "Git", "SQL", "RAG", "Hugging Face"]},
    "Python / Backend Developer": {"match": ["python developer", "backend", "back-end", "back end", "software engineer", "api developer"],
                                   "skills": ["Python", "Flask", "Django", "FastAPI", "REST API", "PostgreSQL", "Docker", "Git",
                                              "Unit Testing", "Redis", "CI/CD", "SQLAlchemy"]},
    "Full-Stack Developer": {"match": ["full stack", "full-stack", "fullstack", "web developer"],
                             "skills": ["JavaScript", "React", "Node.js", "HTML", "CSS", "REST API", "PostgreSQL", "MongoDB",
                                        "Docker", "Git", "CI/CD", "TypeScript"]},
    "Frontend Developer": {"match": ["frontend", "front-end", "front end", "ui developer"],
                           "skills": ["JavaScript", "TypeScript", "React", "HTML", "CSS", "Git", "Unit Testing", "REST API",
                                      "Figma", "Tailwind CSS"]},
    "DevOps / Cloud Engineer": {"match": ["devops", "cloud engineer", "sre", "site reliability", "platform engineer"],
                                "skills": ["AWS", "Docker", "Kubernetes", "Terraform", "CI/CD", "Linux", "Git", "Ansible",
                                           "Prometheus", "Grafana", "Bash", "Python"]},
    "Java Developer": {"match": ["java developer", "java engineer"],
                       "skills": ["Java", "Spring Boot", "SQL", "REST API", "Microservices", "Git", "Unit Testing", "Docker",
                                  "Kafka", "OOP", "Data Structures"]},
    "Mobile Developer": {"match": ["android", "ios developer", "mobile developer", "flutter", "react native"],
                         "skills": ["Kotlin", "Swift", "Flutter", "React Native", "REST API", "Git", "Unit Testing",
                                    "Android", "iOS", "CI/CD"]},
    "Cybersecurity Analyst": {"match": ["security", "cyber"],
                              "skills": ["Cybersecurity", "Linux", "Python", "Penetration Testing", "OAuth", "Bash", "AWS",
                                         "Communication"]},
}


# Canonical names that are also ordinary English words / letters: only their
# explicit aliases are matched (e.g. "golang", "R programming", "express.js").
AMBIGUOUS = {"Go", "R", "Express"}


@lru_cache(maxsize=1)
def _compiled() -> list[tuple[str, re.Pattern]]:
    out = []
    for canon, aliases in SKILLS.items():
        base = set() if canon in AMBIGUOUS else {canon.lower()}
        names = sorted({*base, *[a.lower() for a in aliases]}, key=len, reverse=True)
        alt = "|".join(re.escape(n) for n in names)
        out.append((canon, re.compile(rf"(?<![\w+#.\-/]){'(?:' + alt + ')'}(?![\w+#]|\.\w)", re.IGNORECASE)))
    return out


def extract_skills(text: str) -> dict[str, int]:
    """Return {canonical_skill: occurrence_count} for skills mentioned in text."""
    found: dict[str, int] = {}
    if not text:
        return found
    for canon, pat in _compiled():
        n = len(pat.findall(text))
        if n:
            found[canon] = n
    return found


def match_role(target_role: str) -> tuple[str | None, list[str]]:
    """Map a free-text role to a catalogue role; returns (role_name, skills)."""
    t = (target_role or "").lower()
    best, best_len = None, 0
    for name, info in ROLE_SKILLS.items():
        for kw in info["match"] + [name.lower()]:
            if kw in t and len(kw) > best_len:
                best, best_len = name, len(kw)
    if best:
        return best, list(ROLE_SKILLS[best]["skills"])
    return None, []
