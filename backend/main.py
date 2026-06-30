"""PropertyAI API entry point — configures the FastAPI application and mounts all routers."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.connection import close_engine_async, create_engine_async, get_session_factory
from error_handlers import register_exception_handlers
from redis_store.client import redis_client
from routers.chat import router as chat_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage Redis and PostgreSQL connection lifecycle for the application."""
    await redis_client.connect_async()
    await create_engine_async()
    yield
    await close_engine_async()
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


@app.get("/health", tags=["health"])
async def health_check_async() -> dict[str, object]:
    """Return service liveness status including Redis and PostgreSQL connectivity."""
    redis_ok: bool = await redis_client.ping_async()

    postgres_ok: bool = False
    try:
        factory: async_sessionmaker[AsyncSession] = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception:
        pass

    all_ok: bool = redis_ok and postgres_ok
    status: str = "ok" if all_ok else "degraded"
    return {
        "status": status,
        "version": "0.1.0",
        "services": {
            "redis": "ok" if redis_ok else "error",
            "postgres": "ok" if postgres_ok else "error",
        },
    }
