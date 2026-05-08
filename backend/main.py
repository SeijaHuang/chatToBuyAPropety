"""PropertyAI API entry point — configures the FastAPI application and mounts all routers."""

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from exceptions import LLMServiceError, PropertyAIException, SummaryValidationError
from routers.chat import router as chat_router

load_dotenv()

app = FastAPI(
    title="PropertyAI API",
    version="0.1.0",
)


@app.exception_handler(PropertyAIException)
async def property_ai_exception_handler_async(
    request: Request, exc: PropertyAIException
) -> JSONResponse:
    """Convert PropertyAIException subclasses to the project error envelope.

    LLMServiceError maps to HTTP 503; all other subclasses map to HTTP 500.

    Args:
        request: The incoming HTTP request (unused but required by FastAPI).
        exc: The caught exception.

    Returns:
        JSONResponse with the standard error envelope.
    """
    if isinstance(exc, LLMServiceError):
        status_code = 503
    elif isinstance(exc, SummaryValidationError):
        status_code = 422
    else:
        status_code = 500
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": type(exc).__name__,
                "message": str(exc),
                "details": {},
            }
        },
    )


# Development only — restrict origins before deploying to production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api/v1")


@app.get("/health")
async def health_check_async() -> dict[str, str]:
    """Return service liveness status."""
    return {"status": "ok", "version": "0.1.0"}
