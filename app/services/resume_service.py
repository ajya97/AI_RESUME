"""
Resume storage service: validates uploads, stores the PDF in PRIVATE storage
(outside ``static/``), parses it with the existing parser, and persists a
``Resume`` row owned by the user.
"""

import hashlib
import re
import uuid
from pathlib import Path

import pdfplumber
from flask import current_app
from sqlalchemy import func, select
from werkzeug.utils import secure_filename

from app.core.exceptions import NotFoundError, ResumeParsingError, ValidationError
from app.extensions import db
from app.models.resume import Resume
from app.services.resume_parser_service import parse_resume

MIN_TEXT_CHARS = 80

CONTENT_LIST_KEYS = ("skills", "experience", "education", "projects", "certifications", "achievements")
CONTENT_TEXT_KEYS = ("name", "email", "phone", "linkedin", "github", "location", "summary")


def build_content(parsed: dict) -> dict:
    """Structured, editable content (used by the template library)."""
    content = {k: (parsed.get(k) or "") for k in CONTENT_TEXT_KEYS}
    for k in CONTENT_LIST_KEYS:
        content[k] = list(parsed.get(k) or [])
    return content


def clean_content(raw: dict) -> dict:
    """Validate/normalise user-edited resume content (server-side limits)."""
    if not isinstance(raw, dict):
        raise ValidationError("Invalid resume content.")
    out: dict = {}
    for k in CONTENT_TEXT_KEYS:
        v = raw.get(k, "")
        if not isinstance(v, str):
            raise ValidationError(f"'{k}' must be text.")
        limit = 1500 if k == "summary" else 200
        if len(v) > limit:
            raise ValidationError(f"'{k}' is too long (max {limit} characters).")
        out[k] = v.strip()
    for k in CONTENT_LIST_KEYS:
        v = raw.get(k, [])
        if not isinstance(v, list) or any(not isinstance(i, str) for i in v):
            raise ValidationError(f"'{k}' must be a list of text entries.")
        if len(v) > 40:
            raise ValidationError(f"Too many entries in '{k}' (max 40).")
        limit = 80 if k == "skills" else 2500
        items = []
        for item in v:
            item = item.strip()
            if not item:
                continue
            if len(item) > limit:
                raise ValidationError(f"An entry in '{k}' is too long (max {limit} characters).")
            items.append(item)
        out[k] = items
    return out


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


def user_dir(user_id: int) -> Path:
    d = Path(current_app.config["UPLOAD_FOLDER"]) / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def resume_path(resume: Resume) -> Path:
    return user_dir(resume.user_id) / resume.stored_filename


def save_upload(user, file_storage) -> tuple[Resume, bool]:
    """Validate + store + parse an uploaded PDF. Returns (resume, is_duplicate).

    The same file uploaded twice by one user reuses the existing Resume."""
    if file_storage is None:
        raise ValidationError("No file uploaded")
    filename = file_storage.filename or ""
    if filename == "":
        raise ValidationError("No file selected")
    if not _allowed(filename):
        raise ValidationError("Only PDF files are allowed")

    data = file_storage.read()
    if not data:
        raise ValidationError("The uploaded file is empty.")
    if len(data) > current_app.config["MAX_CONTENT_LENGTH"]:
        raise ValidationError("File too large. Maximum size is 5MB.", status=413, code="file_too_large")
    if not data.startswith(b"%PDF-"):
        raise ValidationError("That file is not a valid PDF.")

    digest = hashlib.sha256(data).hexdigest()
    existing = db.session.execute(
        select(Resume).where(Resume.user_id == user.id, Resume.sha256 == digest)).scalar_one_or_none()
    if existing:
        return existing, True

    count = db.session.execute(select(func.count(Resume.id)).where(Resume.user_id == user.id)).scalar_one()
    if count >= current_app.config["MAX_RESUMES_PER_USER"]:
        raise ValidationError(
            f"You can store up to {current_app.config['MAX_RESUMES_PER_USER']} resumes. Delete one first.",
            code="resume_limit")

    stored = f"{uuid.uuid4().hex}.pdf"
    path = user_dir(user.id) / stored
    path.write_bytes(data)
    try:
        try:
            with pdfplumber.open(str(path)) as pdf:
                pages = len(pdf.pages)
        except Exception as e:
            raise ResumeParsingError(f"Failed to read PDF: {e}")
        if pages > current_app.config["MAX_PDF_PAGES"]:
            raise ValidationError(f"PDF has {pages} pages; the maximum is {current_app.config['MAX_PDF_PAGES']}.")

        parsed = parse_resume(str(path))  # existing parser (raises ResumeParsingError)
        raw_text = parsed.get("raw_text", "")
        if len(raw_text.strip()) < MIN_TEXT_CHARS:
            raise ResumeParsingError(
                "No readable text found in this PDF. Scanned/image-only resumes aren't supported — "
                "export a text-based PDF and try again.")

        public_parsed = {k: v for k, v in parsed.items() if k != "raw_text"}
        safe_name = secure_filename(filename) or "resume.pdf"
        resume = Resume(
            user_id=user.id, original_filename=safe_name[:255], stored_filename=stored,
            file_size=len(data), sha256=digest, page_count=pages, parsed=public_parsed,
            raw_text=raw_text, content=build_content(public_parsed))
        db.session.add(resume)
        db.session.commit()
        return resume, False
    except Exception:
        db.session.rollback()
        path.unlink(missing_ok=True)
        raise


def get_owned_resume(user_id: int, resume_id) -> Resume:
    """Return the resume only if it belongs to the user (else 404 — never reveal existence)."""
    try:
        rid = int(resume_id)
    except (TypeError, ValueError):
        raise ValidationError("A valid resume is required.")
    resume = db.session.execute(
        select(Resume).where(Resume.id == rid, Resume.user_id == user_id)).scalar_one_or_none()
    if resume is None:
        raise NotFoundError("Resume not found.")
    return resume


def delete_resume(resume: Resume) -> None:
    """Delete the stored PDF and the resume row (cascades to its reports,
    interview sessions and chats — they contain data derived from it)."""
    path = resume_path(resume)
    db.session.delete(resume)
    db.session.commit()
    path.unlink(missing_ok=True)


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_download_name(name: str, ext: str) -> str:
    base = _SAFE_NAME.sub("_", name).strip("._") or "resume"
    return f"{base[:80]}.{ext}"
