"""Chat router — exposes /chat and /chat/summary endpoints for the conversation flow."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/chat")
async def chat_async() -> JSONResponse:
    """Handle a single conversation turn and return the assistant reply.

    Returns:
        JSONResponse with the assistant message and updated conversation state.
    """
    # TODO: Implementation: Story S-D
    return JSONResponse(
        status_code=501,
        content={
            "error": {"code": "NOT_IMPLEMENTED", "message": "Not implemented.", "details": {}}
        },
    )


@router.post("/chat/summary")
async def chat_summary_async() -> JSONResponse:
    """Return a structured summary of all collected property requirements.

    Returns:
        JSONResponse containing the formatted requirements summary.
    """
    # TODO: Implementation: Story S-F
    return JSONResponse(
        status_code=501,
        content={
            "error": {"code": "NOT_IMPLEMENTED", "message": "Not implemented.", "details": {}}
        },
    )
