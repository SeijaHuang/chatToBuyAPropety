"""Exception handler registration and structlog configuration for the FastAPI app."""

import logging

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from structlog.processors import CallsiteParameter, CallsiteParameterAdder

from exceptions import PropertyAIException


def configure_logging() -> None:
    """Configure structlog with filename context and JSON-compatible processors."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            CallsiteParameterAdder([CallsiteParameter.FILENAME]),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app and configure logging.

    Args:
        app: The FastAPI application instance.
    """
    configure_logging()
    logger = structlog.get_logger()

    @app.exception_handler(PropertyAIException)
    async def property_ai_exception_handler_async(
        request: Request, exc: PropertyAIException
    ) -> JSONResponse:
        """Convert PropertyAIException subclasses to the project error envelope.

        HTTP status code is read from exc.status_code (defined per exception class).

        Args:
            request: The incoming HTTP request.
            exc: The caught exception.

        Returns:
            JSONResponse with the standard error envelope.
        """
        status_code = exc.status_code
        logger.error(
            "business_exception",
            exc_type=type(exc).__name__,
            message=str(exc),
            status_code=status_code,
            path=request.url.path,
            **exc.details,
        )

        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": type(exc).__name__,
                    "message": str(exc),
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler_async(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Convert Pydantic RequestValidationError to the project error envelope.

        Args:
            request: The incoming HTTP request.
            exc: The caught validation error.

        Returns:
            JSONResponse with the standard error envelope and field-level error list.
        """
        errors = exc.errors()
        logger.warning(
            "request_validation_failed",
            path=request.url.path,
            method=request.method,
            error_count=len(errors),
            errors=errors,
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "RequestValidationError",
                    "message": "Request body failed validation.",
                    "details": {"errors": errors},
                }
            },
        )
