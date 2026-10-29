# API reference

All endpoints require a signed-in session (cookie) unless stated. State-changing requests need the CSRF token in the
`X-CSRFToken` header (the bundled frontend does this). Errors are always `{"error": "<message>", "code": "<code>"}`;
extra fields are listed where relevant. **Billable** endpoints accept an optional `Idempotency-Key` header
(8–80 chars `[A-Za-z0-9_-]`); re-using a key returns `409 duplicate_operation` without a second charge.
Every resource is owner-checked — someone else's id returns `404`.

Common codes: `401 auth_required`, `400 validation_error`, `402 insufficient_credits` (`required`, `balance`),
`404 not_found`, `409 duplicate_operation`, `413 file_too_large`, `422 unreadable_pdf`, `429 rate_limited`,
`502 ai_provider_error | ai_output_invalid`, `503 ai_not_configured`. On any 5xx from a billable call the debit has been **refunded**.

## Resumes
| Method & path | Input | Success response | Credits |
|---|---|---|---|
| `POST /api/upload` *(original contract)* | multipart `resume` (PDF ≤5 MB) | `{success, resume_id, report_id, parsed, ats, missing_sections, errors, gpt_analysis, ats_note, credits}` | **100** (`ats_analysis`) |
| `POST /api/resumes` | multipart `resume` | `201 {success, duplicate, resume}` (`200` if same file already uploaded) | free |
| `GET /api/resumes` | – | `{resumes:[{id, filename, size, pages, name, template, uploaded_at, latest_ats_score}]}` | free |
| `DELETE /api/resumes/<id>` | – | `{success}` – deletes PDF + derived reports/interviews/chats | free |
| `POST /api/resumes/<id>/analyze` | – | same as `/api/upload` | **100** |
| `GET /api/resumes/<id>/content` | – | `{content, template, templates}` | free |
| `PUT /api/resumes/<id>/content` | `{content:{name,email,phone,linkedin,github,location,summary,skills[],experience[],education[],projects[],certifications[],achievements[]}, template}` | `{success, content, template}` | free |
| `GET /api/templates` | – | `{templates:[{key,name,description,accent}]}` | free |
| `GET /api/resumes/<id>/export.pdf?template=` | – | PDF download | free |
| `GET /resumes/<id>/file` | – | the user's own stored PDF (never under `/static`) | free |
| `GET /resumes/<id>/preview/<template>` | – | HTML preview (autoescaped) | free |

## Career
| Method & path | Input | Success response | Credits |
|---|---|---|---|
| `POST /api/job-match` | `{resume_id, job_description (40–8000 chars)}` | `{success, report, credits}`; `report.data = {comparison, advice}` | **50** |
| `POST /api/skill-gap` | `{resume_id, target_role, requirements?}` | `{success, report, credits}`; `report.data = {gap, plan}` | **75** |
| `GET /api/career/roles` | – | `{roles:[...]}` | free |
| `GET /api/reports/<id>` | – | `{report}` | free |
| `DELETE /api/reports/<id>` | – | `{success}` | free |
| `GET /api/reports/<id>/export.pdf` | – | PDF | free |
| `PATCH /api/reports/<id>/progress` | `{skill, status: todo\|in_progress\|done}` | `{success, skill, status, note}` (self-reported) | free |
| `POST /api/chat/sessions` | `{resume_id}` | `201 {success, session}` | free |
| `GET /api/chat/sessions?resume_id=` | – | `{sessions}` | free |
| `GET /api/chat/sessions/<id>` | – | `{session, messages, limit}` | free |
| `DELETE /api/chat/sessions/<id>` | – | `{success}` | free |
| `POST /api/chat/sessions/<id>/messages` | `{message (≤2000 chars)}` | `{success, user_message, message, credits}`; `400 chat_limit` after 100 messages | **10** per message |

## Interview
| Method & path | Input | Success response | Credits |
|---|---|---|---|
| `POST /api/generate-questions` | `{resume_id?, difficulty: Easy\|Medium\|Hard\|Mixed, category: all\|Technical\|HR\|Project-Based\|Scenario-Based, job_description?}` (no `resume_id` → latest resume, as originally) | `{success, session_id, candidate_name, target_role, questions, difficulty, focus, credits, disclaimer}` | **100** per session |
| `POST /api/evaluate-answer` | `{session_id, index, answer (10–4000 chars)}` – question text is read server-side | `{success, evaluation, progress, credits, disclaimer}`; `409` if already answered | **10** per answer |
| `POST /api/interview/<id>/skip` | `{index}` | `{success, progress}` (counts as 0) | free |
| `GET /api/interview-summary?session_id=` | – | `{session_id, status, candidate_name, total_questions_answered, total_questions, average_score, score_label, individual_scores, breakdown}` (`404` if nothing answered) | free |
| `GET /api/interview/sessions` · `GET /api/interview/<id>` | – | sessions / full session with answers | free |
| `POST /api/interview/<id>/retry` | – | `{success, session_id, questions}` – new attempt, same questions | free |
| `DELETE /api/interview/<id>` | – | `{success}` | free |

*Original-contract changes:* `/api/evaluate-answer` now takes `session_id`+`index` instead of browser-supplied `question`/`category`
(prevents tampering and lets the answer be stored); `/api/generate-questions` no longer trusts a browser-supplied `parsed` object.
The bundled frontend was updated accordingly.

## Account, credits, history
| Method & path | Input | Response |
|---|---|---|
| `POST /api/settings/theme` | `{theme: dark\|light}` | `{success, theme}` (saved in PostgreSQL) |
| `GET /api/credits?page=&per_page=` | – | `{balance, costs, labels, transactions:[{type, operation, amount, balance_after, status, description, reference, created_at}]}` |
| `GET /api/history?type=&q=&page=&per_page=` | `type ∈ ats, job_match, skill_gap, interview, chat` | `{items, page, per_page, total, pages}` |
| `GET /api/analytics/summary` | – | totals, average ATS, timelines, skill-gap trend, interview progress, recent activity, credit usage, AI token usage |
| `GET /healthz` *(public)* | – | `{status, database}` (`503` if DB unreachable) |

Page routes: `/`, `/features`, `/login`, `/register`, `/logout` (POST), `/forgot-password`, `/reset-password/<token>`,
`/dashboard`, `/analyze`, `/templates`, `/job-match`, `/skill-gap`, `/interview`, `/chatbot`, `/history`,
`/history/<kind>/<id>`, `/credits`, `/profile`, `/settings`, `/account/delete` (POST).
