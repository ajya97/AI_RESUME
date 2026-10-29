# ResumeAI — AI Resume & Career Copilot

Flask + PostgreSQL SaaS app built on the original *Resume Analyzer*: ATS analysis, job-description matching, skill-gap
analysis, AI interview copilot, resume chatbot, resume templates with PDF export, history & analytics, user accounts and a
credit wallet — with a dark/light theme.

> **Scores are guidance, not guarantees.** The ATS score is a heuristic from this app's own rules (not any employer's
> system). AI feedback is advisory. Skills are *inferred from resume text*, not verified. Nothing here predicts hiring outcomes.

## What was inspected / preserved
The original repo (single commit `24ff66e`) was inspected first; see [`docs/INSPECTION_AND_CHECKLIST.md`](docs/INSPECTION_AND_CHECKLIST.md)
for the verified routes, contracts and the defects found. Preserved: Flask app-factory + blueprints, `pdfplumber` parser,
the 7-dimension ATS scoring, LangChain `ChatOpenAI` integration and its env vars (`OPENAI_API_KEY`, `BASE_URL`, `MODEL_NAME`,
`EVALUATION_MODEL_NAME`), the interview question/evaluation chains, the `/api/upload`, `/api/generate-questions`,
`/api/evaluate-answer`, `/api/interview-summary` endpoints (two request shapes tightened — see `docs/API.md`), vanilla-JS ES modules.
Fixed: hardcoded `SECRET_KEY`, debug-by-default, XSS in the skills renderer, High-priority sort bug, phone-regex false
positives, leaked exception text, public upload folder, trust of browser-supplied resume JSON.

## Features
| Feature | Credits | Notes |
|---|---|---|
| Registration bonus | +1000 | exactly once per user (DB-enforced) |
| ATS analysis | 100 | existing scoring + AI; PDF report |
| Job match | 50 | deterministic score (documented below) + AI advice |
| Skill gap | 75 | inferred skills vs role/requirements; plan; self-reported progress |
| Interview session | 100 (+10 per answer evaluation) | difficulty, category, optional job description; resumable |
| Resume chatbot | 10 per message | grounded in your resume + latest ATS report |
| Templates (4) + editing + PDF export | free | deterministic, no AI |
| History, analytics, reports, deletion | free | computed from real DB rows |

### Credit & charging policy
* **Unit**: one *billable operation* = the price above, set in `CREDIT_COSTS` / env vars (these are application credits, not provider tokens).
* **Reserve-then-refund**: credits are debited (row-locked `SELECT … FOR UPDATE`, atomic) *before* the AI call. If the operation
  fails for any reason (provider error, unusable AI output, DB error while saving) the debit is **refunded automatically**, exactly once
  (`refund_of_id` is UNIQUE). Validation errors are rejected *before* charging.
* Negative balances are impossible (CHECK constraint + lock). Double-clicks are caught by `Idempotency-Key` (unique per user).
* Opening pages, theme changes, viewing reports, template edits/exports are free. Every movement is in the `credit_transactions` ledger.
* Provider token usage + estimated USD cost are stored separately in `ai_usage`.
* No payments / top-ups exist.

### Job-match methodology (deterministic)
Skills found by a fixed vocabulary in the JD and resume; required skills weigh 2, "preferred/nice to have" 1. Score = 60 % skill
match + 25 % keyword coverage + 15 % experience years (only if the JD states years; resume years are *estimated* from date ranges),
re-normalised if a component is unavailable. AI then adds a summary, requirement comparison and tailoring suggestions.

## Project structure
```
run.py                      entry point
app/
  __init__.py               app factory, security headers (CSP nonce), context processors
  config.py                 env-driven config (DATABASE_URL / SECRET_KEY required)
  extensions.py             db, migrate, csrf, login, limiter
  models/                   user, credits(wallet, ledger, ai_usage), resume(+report), interview, chat
  services/                 credit_service, resume_service, report_service, job_match, skill_gap, chat,
                            interview, ats_score, resume_parser, resume_analysis, template, export(PDF), history
  blueprints/               auth, account, pages, resume, career, interview, history
  prompts/ schemas/ core/   LangChain prompts, Pydantic schemas, errors/exceptions/http/mail helpers
migrations/                 Alembic (initial schema)
templates/                  base, public_base, app_base, auth/, dashboard/, resume/, career/, history/, errors/
static/css/                 variables, base, layout, components, auth, dashboard, resume, career, responsive
static/js/                  app.js, core/ (api, theme, ui, charts, ats-render, report-render, resume-picker), pages/
tests/                      103 tests (PostgreSQL + mocked LLM)
docs/                       API.md, INSPECTION_AND_CHECKLIST.md
```

## Setup
Requires **Python 3.12** and **PostgreSQL** (tested on 16; 13+ is expected to work but was not tested).
```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # then edit .env
```
Set in `.env`:
* `DATABASE_URL=postgresql://user:password@host:5432/dbname` (hosted URLs `postgres://…` also work; add `?sslmode=require` for most cloud DBs)
* `SECRET_KEY=` → `python -c "import secrets; print(secrets.token_hex(32))"`
* AI provider: `OPENAI_API_KEY` (and optionally `BASE_URL`, `MODEL_NAME`, `EVALUATION_MODEL_NAME`)
* optional: `MAIL_*` for password-reset email, `INITIAL_USER_CREDITS`, `CREDIT_COST_*`

### Database
```bash
export FLASK_APP=run.py          # Windows: set FLASK_APP=run.py
flask db upgrade                 # creates all tables (migration in migrations/versions)
```
After changing models: `flask db migrate -m "msg"` → review → `flask db upgrade`. Never recreate tables destructively.

### Run
```bash
python run.py                                            # http://127.0.0.1:5000  (dev)
gunicorn -w 4 -b 0.0.0.0:8000 "run:app"                  # production
```
## Tests
Use a **separate disposable** database:
```bash
createdb ai_resume_test
export TEST_DATABASE_URL=postgresql://user:password@localhost:5432/ai_resume_test
pytest -q
```
The suite rebuilds the schema from the Alembic migration, fakes the LLM, and refuses to run if `TEST_DATABASE_URL == DATABASE_URL`.

## Security summary
Hashed passwords (scrypt), rate-limited login (per IP and per account), CSRF on forms and API, signed expiring single-use reset tokens
(only sent if SMTP is configured — otherwise the UI says so), secure/HttpOnly/SameSite cookies, strict CSP with per-request nonce,
owner checks on every resource (404 for others'), private upload folder outside `static/`, PDF magic-byte/size/page validation,
parameterised ORM queries, output escaping everywhere (`textContent`/escape helpers/Jinja autoescape; user content in templates is escaped),
prompt-injection delimiting of untrusted text, no secrets/PII in logs, server-side credit prices only.

## Deployment notes
* Set `FLASK_ENV=production` (secure cookies on by default → serve over HTTPS), `TRUST_PROXY=true` behind a proxy, run `flask db upgrade` on release.
* Use `RATELIMIT_STORAGE_URI=redis://…` with multiple workers (default memory store is per-process).
* Put `UPLOAD_FOLDER` on persistent storage (default `instance/uploads`); back it up together with the database.
* Probe `GET /healthz` for liveness/DB connectivity. Rotate `SECRET_KEY` invalidates sessions and reset links.

## Known limitations
* Scanned/image-only PDFs are rejected (no OCR). PDF export uses standard Latin fonts; other scripts may be replaced with `?`.
* ATS scoring and the skill vocabulary are heuristics (124 skills, 10 role profiles); unknown roles need pasted requirements.
* If the AI provider is down, ATS analysis fails (and is refunded) — there is no AI-less ATS mode.
* Password-reset emails need SMTP (`MAIL_*`); without it the feature honestly reports it cannot send.
* Rate-limit counters are in-memory unless Redis is configured. Google Fonts are loaded from Google's CDN.
