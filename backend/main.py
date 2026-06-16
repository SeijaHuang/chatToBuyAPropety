"""PropertyAI API entry point — configures the FastAPI application and mounts all routers."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from domain.redis.client import redis_client
from error_handlers import register_exception_handlers
from routers.chat import router as chat_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage Redis connection pool lifecycle for the application.

    Opens the Redis connection on startup and closes it cleanly on shutdown.
    """
    await redis_client.connect_async()
    yield
    await redis_client.close_async()


app = FastAPI(
    title="PropertyAI API",
    version="0.1.0",
    lifespan=lifespan,
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
async def health_check_async() -> dict[str, object]:
    """Return service liveness status including Redis connectivity."""
    redis_ok: bool = await redis_client.ping_async()
    status: str = "ok" if redis_ok else "degraded"
    return {
        "status": status,
        "version": "0.1.0",
        "services": {
            "redis": "ok" if redis_ok else "error",
        },
    }
