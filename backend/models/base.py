"""Shared base model for all PropertyAI API DTOs."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class PropertyAIBaseModel(BaseModel):
    """Base model that enforces camelCase aliases for API transport.

    All public DTOs should inherit from this class. The only exception is
    CompletionStatus, whose field names (M1–M4) must not be lowercased by
    the alias generator.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


TData = TypeVar("TData")


class ErrorDetail(PropertyAIBaseModel):
    """Structured error payload carried inside ErrorResponse."""

    code: str
    message: str
    details: dict[str, object] = {}


class ErrorResponse(PropertyAIBaseModel):
    """Standard error envelope returned on all 4xx/5xx responses."""

    ok: Literal[False] = False
    error: ErrorDetail


class SuccessResponse(PropertyAIBaseModel, Generic[TData]):
    """Standard success envelope returned on all 2xx responses."""

    ok: Literal[True] = True
    data: TData
