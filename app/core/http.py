"""Small request helpers shared by API blueprints."""

import re

from flask import request

from app.core.exceptions import ValidationError

_KEY = re.compile(r"^[A-Za-z0-9_\-]{8,80}$")


def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("A JSON request body is required.")
    return data


def idempotency_key() -> str | None:
    """Optional client key (header ``Idempotency-Key``) preventing double charges."""
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        return None
    if not _KEY.match(key):
        raise ValidationError("Invalid Idempotency-Key header.")
    return key


def page_args(default_per_page: int = 10, max_per_page: int = 50) -> tuple[int, int]:
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        per = min(max(int(request.args.get("per_page", default_per_page)), 1), max_per_page)
    except ValueError:
        per = default_per_page
    return page, per
