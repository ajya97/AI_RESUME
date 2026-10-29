# Repository inspection & implementation checklist

Inspected from the real repo (`ajya97/AI_RESUME`, single commit `24ff66e`) before any change.

## Existing implementation (verified from source)

| Area | Finding |
|---|---|
| Entry point | `run.py` → `app.create_app()`; Flask 3 application factory, port 5000 |
| Blueprints | `pages` (`/`, `/features`, `/analyze`, `/interview`), `resume` (`/api`), `interview` (`/api`) |
| API routes | `POST /api/upload` (multipart field `resume`), `POST /api/generate-questions` (JSON `{parsed}`), `POST /api/evaluate-answer` (JSON `{question, answer, category}`), `GET /api/interview-summary` |
| Persistence | **None.** State lives only in the Flask cookie session; uploaded PDFs deleted after parse |
| Auth / users | **None.** Every route is public; no CSRF; no rate limits |
| AI | LangChain `ChatOpenAI` (OpenAI-compatible). Env: `OPENAI_API_KEY`, `BASE_URL`, `MODEL_NAME`, `EVALUATION_MODEL_NAME` |
| ATS scoring | Deterministic heuristic, 7 dimensions, 100 pts (`ats_score_service.py`) + missing-section / error detection |
| Parsing | `pdfplumber` + regex (`resume_parser_service.py`) |
| Frontend | Jinja templates, modular vanilla-JS ES modules, CSS variables, dark/light toggle in `localStorage` only |
| Tests | 2 files, pure-function tests only |
| Dependencies | `requirements.txt` pins Flask, pdfplumber, PyPDF2 (unused), langchain stack, pytest |

## Defects / risks found

1. `SECRET_KEY` falls back to a hardcoded string (`config.py`) and env var is `FLASK_SECRET_KEY`.
2. `DEBUG` defaults to `True`, and `run.py` binds `0.0.0.0` with that value.
3. **XSS**: `analyze.js::renderProfileInfo` inserts resume-derived skills into `innerHTML` unescaped; `renderScoreTags` too.
4. Sort bug: `order[a.priority] || 2` maps "High" (0) to 2, so High-priority suggestions are not sorted first.
5. Error responses leak exception text (`str(e)`) to clients.
6. Error handlers return JSON only (no HTML error pages).
7. `/api/*` endpoints trust browser-supplied `parsed` resume JSON.
8. Uploaded files are written into `static/uploads/` (publicly servable path) before parsing.
9. `extract_phone` regex matches any 7-digit run (years, ids) → false positives.
10. README claims "data never stored" – will change once persistence exists.
11. `PyPDF2` is listed but unused.

## Checklist

- [x] Inspect repo, record contracts & defects
- [ ] Config: `DATABASE_URL` required, separate test DB, env-only secrets, `.env.example`
- [ ] Extensions + models + Alembic migration (users, wallets, credit tx, resumes, reports, interview, chat, AI usage)
- [ ] Auth: register/login/logout/profile/settings/theme, password reset (signed expiring token, SMTP-gated), CSRF, rate limits
- [ ] Credit service: 1000 grant, atomic debit, idempotency, refunds, row locks, history
- [ ] ATS: keep existing logic; add storage, report persistence, PDF export, deletion
- [ ] Job match, skill gap, interview (preserve API), resume chatbot, templates (+PDF), history, analytics
- [ ] Frontend redesign: tokens, dark/light, app shell, all pages, error pages, XSS fixes
- [ ] Tests on real PostgreSQL (+ mocked LLM), migration check, live app smoke test
- [ ] README/docs, ZIP, verification
