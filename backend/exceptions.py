"""Project exception hierarchy — all business errors inherit from PropertyAIException."""


class PropertyAIException(Exception):  # noqa: N818
    """Base exception for all PropertyAI business errors."""


class LLMServiceError(PropertyAIException):
    """Raised when an OpenRouter or model API call fails."""


class StateTransitionError(PropertyAIException):
    """Raised when an invalid module progression is attempted."""


class SummaryValidationError(PropertyAIException):
    """Raised when a summary is requested but all collected data fields are None."""
