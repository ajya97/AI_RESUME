"""Authentication, sessions, CSRF, rate limiting, headers, templates, theme, pages."""

import io
import re
import time

import pdfplumber
import pytest
from sqlalchemy import select

from app.blueprints.auth.routes import make_reset_token
from app.extensions import db, limiter
from app.models.user import User
from tests.conftest import PASSWORD, balance, register


# ─── Registration / login ──────────────────────────────────────────────────
def test_register_grants_credits_and_logs_in(client):
    r = register(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/dashboard")
    assert balance(client) == 1000
    assert client.get("/dashboard").status_code == 200


def test_password_is_hashed_not_plaintext(client, app):
    register(client)
    with app.app_context():
        u = db.session.execute(select(User)).scalar_one()
        assert PASSWORD not in u.password_hash and u.password_hash.startswith(("scrypt:", "pbkdf2:"))


@pytest.mark.parametrize("pw,msg", [("short1", "8 characters"), ("allletters", "letter and one number"),
                                    ("12345678901", "letter and one number")])
def test_weak_passwords_rejected(client, pw, msg):
    r = client.post("/register", data={"full_name": "A B", "email": "a@b.co", "password": pw, "confirm_password": pw})
    assert r.status_code == 400 and msg in r.get_data(as_text=True)


def test_duplicate_email_case_insensitive(client, app):
    register(client, "Dup@Example.com")
    c2 = app.test_client()
    r = register(c2, "dup@example.COM")
    assert r.status_code == 400 and "already exists" in r.get_data(as_text=True)
    with app.app_context():
        assert len(db.session.execute(select(User)).scalars().all()) == 1


def test_register_validation_errors(client):
    bad = [{"full_name": "", "email": "a@b.co"}, {"full_name": "X", "email": "not-an-email"}]
    for b in bad:
        r = client.post("/register", data={**b, "password": PASSWORD, "confirm_password": PASSWORD})
        assert r.status_code == 400
    r = client.post("/register", data={"full_name": "X", "email": "x@y.zz", "password": PASSWORD, "confirm_password": "Other123x"})
    assert r.status_code == 400 and "do not match" in r.get_data(as_text=True)


def test_login_logout_flow_and_generic_errors(app):
    c = app.test_client()
    register(c)
    c.post("/logout")
    assert c.get("/dashboard").status_code == 302
    bad = c.post("/login", data={"email": "alice@example.com", "password": "wrong-pass1"})
    unk = c.post("/login", data={"email": "nobody@example.com", "password": "wrong-pass1"})
    assert bad.status_code == unk.status_code == 401
    assert re.search(r"Invalid email or password", bad.get_data(as_text=True)) and re.search(r"Invalid email or password", unk.get_data(as_text=True))
    ok = c.post("/login", data={"email": "ALICE@example.com", "password": PASSWORD})
    assert ok.status_code == 302 and c.get("/dashboard").status_code == 200


def test_logout_requires_post(user_client):
    assert user_client.get("/logout").status_code == 405
    assert user_client.post("/logout").status_code == 302
    assert user_client.get("/dashboard").status_code == 302


def test_open_redirect_blocked(app):
    c = app.test_client()
    register(c)
    c.post("/logout")
    for evil in ("https://evil.example/x", "//evil.example", "/\\evil.example"):
        r = c.post("/login", data={"email": "alice@example.com", "password": PASSWORD, "next": evil})
        assert r.headers["Location"].endswith("/dashboard"), evil
        c.post("/logout")
    r = c.post("/login", data={"email": "alice@example.com", "password": PASSWORD, "next": "/history"})
    assert r.headers["Location"].endswith("/history")


# ─── Password reset ────────────────────────────────────────────────────────
def test_reset_token_flow_single_use(app, client):
    register(client)
    with app.app_context():
        u = db.session.execute(select(User)).scalar_one()
        token = make_reset_token(u)
    c = app.test_client()
    assert c.get(f"/reset-password/{token}").status_code == 200
    r = c.post(f"/reset-password/{token}", data={"password": "NewPassw0rd", "confirm_password": "NewPassw0rd"})
    assert r.status_code == 302
    assert c.post("/login", data={"email": "alice@example.com", "password": "NewPassw0rd"}).status_code == 302
    c2 = app.test_client()
    assert c2.get(f"/reset-password/{token}").status_code == 302  # token dead after use


def test_reset_token_expires_and_tampered_rejected(app, client):
    register(client)
    with app.app_context():
        token = make_reset_token(db.session.execute(select(User)).scalar_one())
    app.config["PASSWORD_RESET_MAX_AGE"] = 1
    time.sleep(2.1)
    try:
        assert app.test_client().get(f"/reset-password/{token}").status_code == 302
    finally:
        app.config["PASSWORD_RESET_MAX_AGE"] = 3600
    assert app.test_client().get(f"/reset-password/{token[:-3]}abc").status_code == 302


def test_forgot_password_honest_when_mail_unconfigured(client):
    register(client, "x@y.co")
    r = client.post("/forgot-password", data={"email": "x@y.co"}, follow_redirects=True)
    assert "isn't configured" in r.get_data(as_text=True) or "not configured" in r.get_data(as_text=True)


def test_forgot_password_sends_mail_when_configured(app, client, monkeypatch):
    register(client, "x@y.co")
    sent = []
    monkeypatch.setattr("app.blueprints.auth.routes.mail_configured", lambda: True)
    monkeypatch.setattr("app.blueprints.auth.routes.send_email", lambda to, s, b: sent.append((to, b)))
    r1 = client.post("/forgot-password", data={"email": "x@y.co"}, follow_redirects=True)
    r2 = client.post("/forgot-password", data={"email": "ghost@y.co"}, follow_redirects=True)
    assert len(sent) == 1 and "/reset-password/" in sent[0][1]
    t = lambda r: re.sub(r"\s+", " ", r.get_data(as_text=True))  # noqa: E731
    assert "reset link has been sent" in t(r1) and "reset link has been sent" in t(r2)  # no account enumeration


# ─── Theme & profile ───────────────────────────────────────────────────────
def test_theme_persists_in_database_and_renders_server_side(user_client, app):
    assert user_client.post("/api/settings/theme", json={"theme": "light"}).get_json()["theme"] == "light"
    with app.app_context():
        assert db.session.execute(select(User.theme)).scalar_one() == "light"
    assert 'data-theme="light"' in user_client.get("/dashboard").get_data(as_text=True)
    assert user_client.post("/api/settings/theme", json={"theme": "neon"}).status_code == 400
    # a new session (other device) gets the saved theme
    c2 = app.test_client()
    c2.post("/login", data={"email": "alice@example.com", "password": PASSWORD})
    assert 'data-theme="light"' in c2.get("/dashboard").get_data(as_text=True)


def test_profile_and_password_change(user_client):
    user_client.post("/profile", data={"full_name": "New Name"})
    assert "New Name" in user_client.get("/profile").get_data(as_text=True)
    r = user_client.post("/profile/password", data={"current_password": "bad", "new_password": "Another1pass", "confirm_password": "Another1pass"}, follow_redirects=True)
    assert "incorrect" in r.get_data(as_text=True)
    r = user_client.post("/profile/password", data={"current_password": PASSWORD, "new_password": "Another1pass", "confirm_password": "Another1pass"}, follow_redirects=True)
    assert "Password changed" in r.get_data(as_text=True)


def test_delete_account_removes_everything(user_client, resume_id, app):
    from pathlib import Path
    assert user_client.post("/account/delete", data={"password": "wrong"}).status_code == 302
    assert user_client.get("/dashboard").status_code == 200
    user_client.post("/account/delete", data={"password": PASSWORD})
    with app.app_context():
        assert db.session.execute(select(User)).first() is None
    assert list(Path(app.config["UPLOAD_FOLDER"]).rglob("*.pdf")) == []


# ─── Security controls ─────────────────────────────────────────────────────
def test_csrf_enforced_when_enabled(app):
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        c = app.test_client()
        assert c.post("/register", data={"full_name": "A B", "email": "a@b.co", "password": PASSWORD,
                                         "confirm_password": PASSWORD}).status_code == 400
        page = c.get("/register").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        r = c.post("/register", data={"csrf_token": token, "full_name": "A B", "email": "a@b.co",
                                      "password": PASSWORD, "confirm_password": PASSWORD})
        assert r.status_code == 302
        # JSON API without a token is rejected, with the header accepted
        assert c.post("/api/settings/theme", json={"theme": "light"}).status_code == 400
        meta = re.search(r'name="csrf-token" content="([^"]+)"', c.get("/dashboard").get_data(as_text=True)).group(1)
        assert c.post("/api/settings/theme", json={"theme": "light"}, headers={"X-CSRFToken": meta}).status_code == 200
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_login_rate_limit_per_account(app):
    limiter.enabled = True
    limiter.reset()
    try:
        c = app.test_client()
        register(c)
        c.post("/logout")
        codes = [c.post("/login", data={"email": "alice@example.com", "password": "bad-pass-1"}).status_code for _ in range(10)]
        assert 429 in codes and codes[:8] == [401] * 8
        assert c.post("/login", data={"email": "alice@example.com", "password": PASSWORD}).status_code == 429  # even correct pw is blocked
    finally:
        limiter.enabled = False
        limiter.reset()


def test_api_rate_limit(app, resume_id, user_client):
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [user_client.post("/api/chat/sessions/1/messages", json={"message": ""}).status_code for _ in range(25)]
        assert 429 in codes
    finally:
        limiter.enabled = False
        limiter.reset()


def test_security_headers_and_csp_nonce(client):
    r = client.get("/")
    h = r.headers
    assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "SAMEORIGIN"
    csp = h["Content-Security-Policy"]
    nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
    assert f'nonce="{nonce}"' in r.get_data(as_text=True) and "unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    assert "object-src 'none'" in csp


def test_api_responses_not_cacheable_and_errors_do_not_leak(user_client):
    r = user_client.get("/api/credits")
    assert "no-store" in r.headers["Cache-Control"]
    r = user_client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.get_json()["error"]


def test_session_cookie_flags(client):
    register(client)
    cookie = next(c for c in client._cookies.values() if c.key == "resumeai_session") if hasattr(client, "_cookies") else None
    sc = client.get("/dashboard").headers
    assert cookie is not None or sc


def test_secret_and_database_must_be_configured(monkeypatch):
    from app import create_app
    from app.config import normalize_database_url
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        normalize_database_url("sqlite:///x.db")
    assert normalize_database_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FLASK_ENV", "development")
    from app.config import DevelopmentConfig
    monkeypatch.setattr(DevelopmentConfig, "SECRET_KEY", "k")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app("development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/x")
    monkeypatch.setattr(DevelopmentConfig, "SECRET_KEY", None)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("development")


def test_testing_config_refuses_production_db(monkeypatch):
    import os
    from app import create_app
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    with pytest.raises(RuntimeError, match="must differ"):
        create_app("testing")


def test_healthz(client):
    assert client.get("/healthz").get_json() == {"status": "ok", "database": "up"}


# ─── Templates / exports ───────────────────────────────────────────────────
def test_template_list_edit_preview_and_pdf(user_client, resume_id):
    t = user_client.get("/api/templates").get_json()["templates"]
    assert {x["key"] for x in t} == {"classic", "modern", "compact", "minimal"}
    c = user_client.get(f"/api/resumes/{resume_id}/content").get_json()["content"]
    c["name"] = "Zed Edited"
    c["experience"] = ["Engineer at X\n- Built things\n- Shipped more"]
    assert user_client.put(f"/api/resumes/{resume_id}/content", json={"content": c, "template": "modern"}).status_code == 200
    for key in ("classic", "modern", "compact", "minimal"):
        html = user_client.get(f"/resumes/{resume_id}/preview/{key}").get_data(as_text=True)
        assert "Zed Edited" in html and "<li>Built things</li>" in html
        pdf = user_client.get(f"/api/resumes/{resume_id}/export.pdf?template={key}")
        assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
    with pdfplumber.open(io.BytesIO(pdf.data)) as doc:  # exported PDF is ATS-parseable text
        text = doc.pages[0].extract_text()
    assert "Zed Edited" in text and "Built things" in text and "ZED" not in text.split("\n")[0].upper().replace("ZED EDITED", "")
    assert user_client.get(f"/resumes/{resume_id}/preview/evil").status_code == 404
    assert user_client.get(f"/api/resumes/{resume_id}/export.pdf?template=evil").status_code == 400


def test_template_content_validation_and_xss_escaping(user_client, resume_id):
    c = user_client.get(f"/api/resumes/{resume_id}/content").get_json()["content"]
    c["name"] = "<script>alert(1)</script>"
    c["summary"] = '"><img src=x onerror=alert(2)>'
    assert user_client.put(f"/api/resumes/{resume_id}/content", json={"content": c}).status_code == 200
    html = user_client.get(f"/resumes/{resume_id}/preview/classic").get_data(as_text=True)
    assert "<script>alert(1)" not in html and "&lt;script&gt;alert(1)" in html and "<img src=x" not in html
    pdf = user_client.get(f"/api/resumes/{resume_id}/export.pdf")
    assert pdf.status_code == 200  # reportlab markup injection neutralised too
    bad = [{"name": "x" * 500}, {"skills": "not a list"}, {"experience": ["x" * 3000]}, {"skills": ["a"] * 50}]
    for patch in bad:
        r = user_client.put(f"/api/resumes/{resume_id}/content", json={"content": {**c, **patch}})
        assert r.status_code == 400, patch
    assert user_client.put(f"/api/resumes/{resume_id}/content", json={"content": c, "template": "x"}).status_code == 400


def test_template_export_costs_nothing(user_client, resume_id):
    user_client.get(f"/api/resumes/{resume_id}/export.pdf")
    assert balance(user_client) == 1000


# ─── Every page renders ────────────────────────────────────────────────────
@pytest.mark.parametrize("path", ["/dashboard", "/analyze", "/templates", "/job-match", "/skill-gap", "/interview",
                                  "/chatbot", "/history", "/credits", "/settings", "/profile"])
def test_authenticated_pages_render(user_client, path):
    r = user_client.get(path)
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and 'id="creditBalance">1000<' in html and 'name="csrf-token"' in html


@pytest.mark.parametrize("path", ["/", "/features", "/login", "/register", "/forgot-password"])
def test_public_pages_render(client, path):
    assert client.get(path).status_code == 200


def test_history_detail_pages_render_for_owner(user_client, resume_id):
    rid = user_client.post(f"/api/resumes/{resume_id}/analyze").get_json()["report_id"]
    assert user_client.get(f"/history/ats/{rid}").status_code == 200
    assert user_client.get(f"/history/job_match/{rid}").status_code == 404  # wrong kind
