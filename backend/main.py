"""PropertyAI API entry point — configures the FastAPI application and mounts all routers."""

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from error_handlers import register_exception_handlers
from routers.chat import router as chat_router

load_dotenv()

app = FastAPI(
    title="PropertyAI API",
    version="0.1.0",
)

register_exception_handlers(app)

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
