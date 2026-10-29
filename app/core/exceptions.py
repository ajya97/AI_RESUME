"""Application-level exceptions.

``AppError`` subclasses carry an HTTP status and a stable machine-readable
``code`` so every API endpoint reports failures in one consistent shape::

    {"error": "<human message>", "code": "<machine_code>", ...extra}
"""


class AppError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message: str | None = None, *, status: int | None = None,
                 code: str | None = None, **extra):
        super().__init__(message or self.__doc__ or "Request failed")
        self.message = message or self.__doc__ or "Request failed"
        if status is not None:
            self.status = status
        if code is not None:
            self.code = code
        self.extra = extra

    def to_dict(self) -> dict:
        return {"error": self.message, "code": self.code, **self.extra}


class ValidationError(AppError):
    """Invalid input."""
    status = 400
    code = "validation_error"


class NotFoundError(AppError):
    """Resource not found."""
    status = 404
    code = "not_found"


class ResumeParsingError(ValueError):
    """Raised when a resume PDF cannot be parsed (HTTP 422, as in the
    original /api/upload contract)."""


class InsufficientCreditsError(AppError):
    """Not enough credits for this operation."""
    status = 402
    code = "insufficient_credits"


class DuplicateOperationError(AppError):
    """This operation was already submitted."""
    status = 409
    code = "duplicate_operation"


class AIProviderError(AppError):
    """The AI provider failed or is not configured."""
    status = 502
    code = "ai_provider_error"


class AIOutputError(AppError):
    """The AI provider returned output that could not be used."""
    status = 502
    code = "ai_output_invalid"
