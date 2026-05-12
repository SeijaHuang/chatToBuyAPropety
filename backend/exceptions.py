"""Project exception hierarchy — all business errors inherit from PropertyAIException."""


class PropertyAIException(Exception):  # noqa: N818
    """Base exception for all PropertyAI business errors.

    Args:
        message: Human-readable description of the error.
        status_code: HTTP status code this exception maps to.
        details: Structured context for debugging (model, round, status code, etc.).
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details: dict[str, object] = details or {}


class LLMServiceError(PropertyAIException):
    """Raised when an OpenRouter or model API call fails."""

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message, status_code=503, details=details)


class StateTransitionError(PropertyAIException):
    """Raised when an invalid module progression is attempted."""


class SummaryValidationError(PropertyAIException):
    """Raised when a summary is requested but all collected data fields are None."""

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message, status_code=422, details=details)


class BadRequestError(PropertyAIException):
    """Raised for malformed requests that fail business-level validation (not Pydantic validation)."""

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message, status_code=400, details=details or {})


class RateLimitError(PropertyAIException):
    """Raised when the upstream LLM provider returns a rate-limit response."""

    def __init__(self, retry_after: int = 2) -> None:
        super().__init__(
            "LLM rate limit reached. Please retry shortly.",
            status_code=429,
            details={"retry_after": retry_after},
        )
