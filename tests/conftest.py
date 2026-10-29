"""
Shared pytest fixtures.

* Tests run against a REAL PostgreSQL database given by TEST_DATABASE_URL
  (never DATABASE_URL). The schema is created by running the Alembic
  migration, so the migration itself is exercised on every test run.
* The LLM is replaced by a deterministic fake chat model (no network, no cost)
  that can also emit token-usage metadata or fail on demand.
"""

import io
import json
import os
import shutil

import pytest
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("TEST_DATABASE_URL"):
    pytest.exit("TEST_DATABASE_URL is not set. Point it at a dedicated, disposable PostgreSQL database "
                "(see .env.example).", returncode=2)

os.environ["FLASK_ENV"] = "testing"

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402
from sqlalchemy import text  # noqa: E402

from ..app import create_app  # noqa: E402
from ..app.extensions import db  # noqa: E402


# ─── Fake LLM ──────────────────────────────────────────────────────────────
class FakeLLMState:
    mode = "ok"          # ok | error | garbage | empty
    calls = 0
    last_prompt = ""


def _analysis_json():
    return {
        "target_role": "Backend Developer", "profile_summary": "A solid early-career developer.",
        "skill_gap_analysis": {"strong_skills": ["Python"], "weak_areas": ["Testing"],
                               "missing_critical_skills": ["Kubernetes"],
                               "recommended_skills_to_learn": [{"skill": "Kubernetes", "reason": "Deploys", "resource": "Docs"}]},
        "keyword_recommendations": {"missing_ats_keywords": ["CI/CD"], "recommended_technical_keywords": ["REST"],
                                    "industry_keywords": ["Agile"], "role_specific_keywords": ["Flask"]},
        "improvement_suggestions": [{"priority": "High", "category": "Content", "suggestion": "Quantify results."},
                                    {"priority": "Low", "category": "Formatting", "suggestion": "Tidy spacing."}],
        "interview_readiness": {"score": 72, "strengths": ["Projects"], "weak_points": ["Metrics"],
                                "preparation_tips": ["Practice STAR"]},
        "resume_strength_score": 70, "overall_feedback": "Good start, add metrics.",
    }


def _questions_json():
    cats = ["Technical", "HR", "Project-Based", "Scenario-Based"]
    qs = [{"id": i + 1, "category": cats[i % 4], "difficulty": "Medium",
           "question": f"Question {i + 1} about your experience?", "what_to_look_for": "Specifics",
           "follow_up": "Can you elaborate?"} for i in range(16)]
    return {"candidate_name": "Jane Developer", "target_role": "Backend Developer", "questions": qs}


def _eval_json():
    return {"score": 7, "score_label": "Good", "strengths": ["Clear"], "weaknesses": ["Short"],
            "detailed_feedback": "Solid answer.", "model_answer": "Cover X, Y, Z.",
            "tips_for_improvement": "Add metrics.", "follow_up_suggested": True}


def _job_advice_json():
    return {"summary": "Reasonable fit.", "requirement_comparison": [
                {"requirement": "Python", "status": "met", "note": "Listed"}],
            "tailored_suggestions": [{"section": "Skills", "suggestion": "Add Kubernetes if true.",
                                      "example_bullet": "Suggested: Deployed services with Docker."}],
            "keywords_to_add": ["Kubernetes"]}


def _plan_json():
    return {"summary": "Focus on cloud skills.",
            "learning_plan": [{"skill": "Kubernetes", "priority": "High", "why": "Required", "estimated_weeks": 6,
                               "resources": ["Official docs"], "practice_task": "Deploy an app"},
                              {"skill": "Terraform", "priority": "Medium", "why": "Infra as code", "estimated_weeks": 4,
                               "resources": [], "practice_task": ""}],
            "project_ideas": [{"title": "Deploy Flask on K8s", "description": "Containerise and deploy.",
                               "skills_practiced": ["Docker", "Kubernetes"], "difficulty": "Intermediate"}]}


class FakeChat(BaseChatModel):
    model: str = "fake-model"

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        FakeLLMState.calls += 1
        prompt = "\n".join(str(m.content) for m in messages)
        FakeLLMState.last_prompt = prompt
        if FakeLLMState.mode == "error":
            raise RuntimeError("simulated provider outage (secret internal detail)")
        if FakeLLMState.mode == "garbage":
            body = "this is not json at all"
        elif FakeLLMState.mode == "empty":
            body = ""
        elif "Evaluate this answer" in prompt:
            body = json.dumps(_eval_json())
        elif "generate exactly" in prompt:
            body = json.dumps(_questions_json())
        elif "Analyze the following resume data" in prompt:
            body = json.dumps(_analysis_json())
        elif "DETERMINISTIC COMPARISON" in prompt and "Matched skills" in prompt:
            body = json.dumps(_job_advice_json())
        elif "DETERMINISTIC COMPARISON" in prompt and "TARGET ROLE" in prompt:
            body = json.dumps(_plan_json())
        elif "<user_message>" in prompt:
            body = "Suggested: highlight your Flask project with metrics."
        else:
            body = "{}"
        msg = AIMessage(content=body, usage_metadata={"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500},
                        response_metadata={"model_name": self.model})
        return ChatResult(generations=[ChatGeneration(message=msg)])


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    FakeLLMState.mode, FakeLLMState.calls, FakeLLMState.last_prompt = "ok", 0, ""
    monkeypatch.setattr("app.services.llm_client.ChatOpenAI", FakeChat)
    return FakeLLMState


# ─── App / DB ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def app():
    application = create_app("testing")
    from app.extensions import limiter
    limiter.enabled = False  # individual tests switch it on when they test rate limits
    with application.app_context():
        db.session.execute(text("DROP SCHEMA public CASCADE"))
        db.session.execute(text("CREATE SCHEMA public"))
        db.session.commit()
        from flask_migrate import upgrade
        upgrade(directory=os.path.join(os.path.dirname(__file__), "..", "migrations"))
    yield application
    shutil.rmtree(application.config["UPLOAD_FOLDER"], ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_db(app):
    yield
    with app.app_context():
        db.session.remove()
        names = ", ".join(t.name for t in db.metadata.sorted_tables)
        db.session.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        db.session.commit()
        db.session.remove()
    shutil.rmtree(app.config["UPLOAD_FOLDER"], ignore_errors=True)
    app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)


@pytest.fixture()
def ctx(app):
    with app.app_context():
        yield
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


PASSWORD = "Str0ngPass1"


def register(client, email="alice@example.com", name="Alice Tester", password=PASSWORD):
    return client.post("/register", data={"full_name": name, "email": email, "password": password,
                                          "confirm_password": password}, follow_redirects=False)


@pytest.fixture()
def user_client(app):
    c = app.test_client()
    r = register(c)
    assert r.status_code == 302, r.data
    return c


@pytest.fixture()
def second_client(app):
    c = app.test_client()
    r = register(c, "bob@example.com", "Bob Tester")
    assert r.status_code == 302
    return c


# ─── Sample PDF ────────────────────────────────────────────────────────────
def make_resume_pdf(name="Jane Developer", extra="") -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800

    def line(text, size=10):
        nonlocal y
        c.setFont("Helvetica", size)
        c.drawString(50, y, text)
        y -= 16

    line(name, 18)
    line("jane.developer@example.com | +1 415-555-0134")
    line("linkedin.com/in/janedeveloper | github.com/janedev")
    y -= 6
    for text in ["Summary", "Backend developer who builds reliable Flask services.", "", "Skills",
                 "Python, Flask, SQL, PostgreSQL, Docker, Git, REST API, JavaScript, Pandas, Linux", "",
                 "Experience", "Backend Intern at Acme Corp 2022 - 2023",
                 "Developed REST APIs serving 5000 users and improved speed by 30%.",
                 "Built CI pipelines and implemented unit tests with pytest.", "",
                 "Backend Engineer at Beta Ltd 2023 - Present",
                 "Optimized PostgreSQL queries and launched 3 features.", "",
                 "Education", "B.Tech Computer Science, State University, CGPA 8.4", "",
                 "Projects", "Resume Analyzer built with Flask and deployed on a cloud host, github.com/janedev/ra", "",
                 "Certifications", "AWS Cloud Practitioner", "Google Data Analytics", ""]:
        line(text)
    if extra:
        line(extra)
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture()
def pdf_bytes():
    return make_resume_pdf()


def upload(client, data: bytes, filename="resume.pdf", url="/api/resumes", headers=None):
    return client.post(url, data={"resume": (io.BytesIO(data), filename)},
                       content_type="multipart/form-data", headers=headers or {})


@pytest.fixture()
def resume_id(user_client, pdf_bytes):
    r = upload(user_client, pdf_bytes)
    assert r.status_code == 201, r.data
    return r.get_json()["resume"]["id"]


def balance(client) -> int:
    return client.get("/api/credits").get_json()["balance"]
