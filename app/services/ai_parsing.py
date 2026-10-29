"""Shared helper: parse model output into a Pydantic schema or fail loudly."""

import json
import re

from pydantic import BaseModel

from app.core.exceptions import AIOutputError


def strip_fences(raw: str) -> str:
    return raw.replace("```json", "").replace("```", "").strip()


def parse_model_output(raw: str, schema: type[BaseModel]) -> dict:
    """Parse ``raw`` into ``schema`` and return a plain dict.

    Raises AIOutputError (so the caller's credit charge is refunded) instead of
    fabricating a fallback result."""
    text = strip_fences(raw or "")
    # tolerate leading/trailing prose around a JSON object
    if not text.startswith("{"):
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
    try:
        return schema.model_validate(json.loads(text)).model_dump()
    except Exception:
        raise AIOutputError("The AI returned a response we couldn't read. Your credits were refunded; please try again.")
