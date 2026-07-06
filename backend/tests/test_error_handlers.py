"""Tests for the global exception handlers registered in error_handlers.py."""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from error_handlers import register_exception_handlers


def _make_app() -> FastAPI:
    """Return a minimal FastAPI app with a route that raises an unregistered exception."""
    app: FastAPI = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom_async() -> None:
        raise RuntimeError("unexpected failure")

    return app


async def test_unhandled_exception_returns_standard_error_envelope() -> None:
    """A RuntimeError with no dedicated handler is converted to the standard envelope."""
    app: FastAPI = _make_app()
    transport: ASGITransport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    error: dict[str, object] = response.json()["error"]
    assert response.json()["ok"] is False
    assert error["code"] == "InternalServerError"
    assert error["message"]
