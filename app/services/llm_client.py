"""
LangChain chat model factory + usage-tracking invocation helper.

Centralises construction of the ChatOpenAI client so every chain in the app
(analysis, interview, job match, skill gap, chat) shares one configuration.
Works with any OpenAI-compatible endpoint (``BASE_URL``).
"""

from flask import current_app, g
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_openai import ChatOpenAI

from app.core.exceptions import AIProviderError


def get_chat_model(model_name: str | None = None, temperature: float = 0.4, max_tokens: int = 2000) -> ChatOpenAI:
    """Build a ChatOpenAI instance from app config.

    Raises AIProviderError (HTTP 503, code ai_not_configured) if neither
    OPENAI_API_KEY nor BASE_URL is configured — same validation as the
    original implementation, but with a clean API error.
    """
    api_key = current_app.config.get("OPENAI_API_KEY")
    base_url = current_app.config.get("OPENAI_BASE_URL")

    if not api_key and not base_url:
        raise AIProviderError(
            "The AI provider is not configured on the server (set OPENAI_API_KEY or BASE_URL).",
            status=503, code="ai_not_configured")

    resolved_model = model_name or current_app.config.get("MODEL_NAME") or "openrouter/free"
    current_app.logger.debug(
        "Initializing ChatOpenAI (base_url=%s, api_key=%s, model=%s)",
        base_url, "set" if api_key else "not set", resolved_model)

    return ChatOpenAI(
        model=resolved_model,
        api_key=api_key or "not-needed",
        base_url=base_url or "https://openrouter.ai/api/v1",
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=current_app.config.get("LLM_TIMEOUT_SECONDS", 60),
        max_retries=1,
    )


def invoke_chain(chain, inputs: dict) -> str:
    """Run a chain, capture provider-reported token usage into ``g.ai_usage``
    (persisted by credit_service.billable) and translate provider failures into
    a clean AIProviderError (no internal details leak to the client)."""
    handler = UsageMetadataCallbackHandler()
    try:
        return chain.invoke(inputs, config={"callbacks": [handler]})
    except AIProviderError:
        raise
    except Exception:
        current_app.logger.exception("LLM call failed")
        raise AIProviderError("The AI provider request failed. Please try again in a moment.")
    finally:
        try:
            if not hasattr(g, "ai_usage") or g.ai_usage is None:
                g.ai_usage = []
            for model, usage in (handler.usage_metadata or {}).items():
                g.ai_usage.append({
                    "model": model,
                    "input_tokens": int(usage.get("input_tokens", 0) or 0),
                    "output_tokens": int(usage.get("output_tokens", 0) or 0),
                })
        except Exception:  # pragma: no cover
            current_app.logger.debug("usage capture failed", exc_info=True)
