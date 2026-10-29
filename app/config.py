"""
Application configuration.

Every setting comes from environment variables (see ``.env.example``). There
are no hardcoded secrets and no silent database fallbacks: if ``DATABASE_URL``
or ``SECRET_KEY`` is missing the app refuses to start with a clear message.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env here (not just in the factory) so class-level os.getenv() calls
# always see it regardless of import order.
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str):
    raw = os.getenv(name)
    try:
        return float(raw) if raw not in (None, "") else None
    except ValueError:
        return None


def normalize_database_url(url: str | None) -> str | None:
    """Return a SQLAlchemy URL using the psycopg (v3) driver.

    Accepts the ``postgres://`` / ``postgresql://`` forms that hosting
    providers emit. Anything that is not PostgreSQL is rejected so that the
    app can never silently run on SQLite or an in-memory database.
    """
    if not url:
        return None
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "DATABASE_URL must be a PostgreSQL URL, e.g. "
            "postgresql://user:password@host:5432/dbname"
        )
    return url


class Config:
    """Base configuration shared by all environments."""

    ENV_NAME = "base"
    TESTING = False
    DEBUG = _bool("FLASK_DEBUG", False)

    # --- Secrets / database (validated in init_app) -----------------------
    SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("FLASK_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = None  # set by init_app from DATABASE_URL
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_size": _int("DB_POOL_SIZE", 5),
        "max_overflow": _int("DB_MAX_OVERFLOW", 10),
        "pool_recycle": _int("DB_POOL_RECYCLE", 1800),
        "pool_timeout": _int("DB_POOL_TIMEOUT", 30),
        "connect_args": {"connect_timeout": _int("DB_CONNECT_TIMEOUT", 10)},
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Sessions / cookies ----------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    SESSION_COOKIE_NAME = "resumeai_session"
    PERMANENT_SESSION_LIFETIME = _int("SESSION_LIFETIME_HOURS", 24 * 7) * 3600
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    WTF_CSRF_TIME_LIMIT = None  # token valid for the session lifetime
    WTF_CSRF_HEADERS = ["X-CSRFToken", "X-CSRF-Token"]

    # --- Uploads -----------------------------------------------------------
    # Private storage OUTSIDE static/ so resumes are never publicly servable.
    UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER", BASE_DIR / "instance" / "uploads"))
    ALLOWED_EXTENSIONS = {"pdf"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
    MAX_PDF_PAGES = _int("MAX_PDF_PAGES", 10)
    MAX_RESUMES_PER_USER = _int("MAX_RESUMES_PER_USER", 20)

    # --- LLM / LangChain (existing integration, unchanged names) ----------
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv("BASE_URL") or None
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
    # Preserved from the original implementation (answer evaluation model).
    EVALUATION_MODEL_NAME = os.getenv("EVALUATION_MODEL_NAME", "gpt-4o-mini")
    LLM_TIMEOUT_SECONDS = _int("LLM_TIMEOUT_SECONDS", 60)
    # Optional provider price (USD per 1M tokens) used ONLY to estimate
    # provider cost in the ai_usage table. Not related to credits.
    MODEL_INPUT_PRICE_PER_1M = _float("MODEL_INPUT_PRICE_PER_1M")
    MODEL_OUTPUT_PRICE_PER_1M = _float("MODEL_OUTPUT_PRICE_PER_1M")

    # --- Credits -----------------------------------------------------------
    INITIAL_USER_CREDITS = _int("INITIAL_USER_CREDITS", 1000)
    CREDIT_COSTS = {
        "ats_analysis": _int("CREDIT_COST_ATS_ANALYSIS", 100),
        "job_match": _int("CREDIT_COST_JOB_MATCH", 50),
        "skill_gap": _int("CREDIT_COST_SKILL_GAP", 75),
        "interview_session": _int("CREDIT_COST_INTERVIEW_SESSION", 100),
        "interview_evaluation": _int("CREDIT_COST_INTERVIEW_EVALUATION", 10),
        "chat_message": _int("CREDIT_COST_CHAT_MESSAGE", 10),
    }

    # --- Limits ------------------------------------------------------------
    MAX_JOB_DESCRIPTION_CHARS = _int("MAX_JOB_DESCRIPTION_CHARS", 8000)
    MAX_CHAT_MESSAGE_CHARS = _int("MAX_CHAT_MESSAGE_CHARS", 2000)
    MAX_CHAT_MESSAGES_PER_SESSION = _int("MAX_CHAT_MESSAGES_PER_SESSION", 100)
    MAX_INTERVIEW_ANSWER_CHARS = _int("MAX_INTERVIEW_ANSWER_CHARS", 4000)

    # --- Rate limiting -----------------------------------------------------
    RATELIMIT_ENABLED = _bool("RATELIMIT_ENABLED", True)
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    # --- Email (password reset) -------------------------------------------
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = _int("MAIL_PORT", 587)
    MAIL_USE_TLS = _bool("MAIL_USE_TLS", True)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_FROM = os.getenv("MAIL_FROM")
    PASSWORD_RESET_MAX_AGE = _int("PASSWORD_RESET_MAX_AGE_SECONDS", 3600)
    APP_BASE_URL = os.getenv("APP_BASE_URL", "").rstrip("/")

    @classmethod
    def mail_configured(cls) -> bool:
        return bool(cls.MAIL_SERVER and cls.MAIL_FROM)

    @classmethod
    def database_url(cls) -> str | None:
        return normalize_database_url(os.getenv("DATABASE_URL"))

    @classmethod
    def init_app(cls, app):
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError(
                "SECRET_KEY is not set. Generate one with: "
                "python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            url = cls.database_url()
            if not url:
                raise RuntimeError(
                    "DATABASE_URL is not set. Provide a PostgreSQL URL, e.g. "
                    "postgresql://user:password@host:5432/dbname (see .env.example)."
                )
            app.config["SQLALCHEMY_DATABASE_URI"] = url
        Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    ENV_NAME = "development"


class ProductionConfig(Config):
    ENV_NAME = "production"
    DEBUG = False
    # Secure cookies by default in production; override only for plain-HTTP
    # staging with SESSION_COOKIE_SECURE=false.
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", True)
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE


class TestingConfig(Config):
    """Uses TEST_DATABASE_URL only — never DATABASE_URL."""

    ENV_NAME = "testing"
    TESTING = True
    SECRET_KEY = "test-only-secret-key-not-for-production"
    # Limiter stays initialised (so tests can switch it on); conftest sets limiter.enabled = False.
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    UPLOAD_FOLDER = Path(os.getenv("TEST_UPLOAD_FOLDER", BASE_DIR / "instance" / "test_uploads"))
    OPENAI_API_KEY = "test-key"
    MODEL_INPUT_PRICE_PER_1M = 0.15
    MODEL_OUTPUT_PRICE_PER_1M = 0.60

    @classmethod
    def init_app(cls, app):
        test_url = normalize_database_url(os.getenv("TEST_DATABASE_URL"))
        if not test_url:
            raise RuntimeError(
                "TEST_DATABASE_URL is not set. Tests need a dedicated PostgreSQL "
                "database (never the production DATABASE_URL)."
            )
        prod = normalize_database_url(os.getenv("DATABASE_URL"))
        if prod and prod == test_url:
            raise RuntimeError("TEST_DATABASE_URL must differ from DATABASE_URL.")
        app.config["SQLALCHEMY_DATABASE_URI"] = test_url
        super().init_app(app)


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
