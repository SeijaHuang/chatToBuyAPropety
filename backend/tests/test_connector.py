"""Tests for agent.shared.connector — exception hierarchy, ConnectorConfig, BaseConnector."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from agent.connector.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorError,
    ConnectorHttpError,
    ConnectorTimeoutError,
)
from exceptions import PropertyAIException

# ============================================================================
# Concrete subclass for testing BaseConnector
# ============================================================================


class FakeConnector(BaseConnector):
    """Minimal concrete connector for testing BaseConnector."""

    async def _build_auth_async(self, request: httpx.Request) -> httpx.Request:
        request.headers["Authorization"] = "Bearer test-token"
        return request

    def _map_error(self, status_code: int, response_body: str) -> str:
        return f"FAKE_{status_code}"


# ============================================================================
# Helpers
# ============================================================================


def _make_mock_response(
    status_code: int = 200,
    json_data: dict[str, object] | None = None,
    text: str = "",
) -> MagicMock:
    """Build a MagicMock that quacks like httpx.Response."""
    resp: MagicMock = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data if json_data is not None else {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        http_error: httpx.HTTPStatusError = httpx.HTTPStatusError(
            f"{status_code} Error",
            request=MagicMock(spec=httpx.Request),
            response=resp,
        )
        resp.raise_for_status.side_effect = http_error
    return resp


def _make_connector() -> FakeConnector:
    """Return a FakeConnector with default config."""
    config: ConnectorConfig = ConnectorConfig(base_url="https://api.example.com")
    return FakeConnector(config=config)


# ============================================================================
# ConnectorError (existing Subtask 1 tests)
# ============================================================================


class TestConnectorError:
    """ConnectorError base class tests."""

    def test_connector_error_is_exception_not_property_ai(self) -> None:
        """ConnectorError inherits from Exception, not PropertyAIException."""
        err: ConnectorError = ConnectorError()
        assert isinstance(err, Exception)
        assert not isinstance(err, PropertyAIException)


class TestConnectorHttpError:
    """ConnectorHttpError tests."""

    def test_fields_assigned_correctly(self) -> None:
        """Constructor assigns status_code, error_code, and response_body."""
        err: ConnectorHttpError = ConnectorHttpError(
            status_code=429,
            error_code="PTV_RATE_LIMITED",
            response_body='{"error": "Too many requests"}',
        )
        assert err.status_code == 429
        assert err.error_code == "PTV_RATE_LIMITED"
        assert err.response_body == '{"error": "Too many requests"}'

    def test_is_instance_of_connector_error(self) -> None:
        """ConnectorHttpError is a subclass of ConnectorError."""
        err: ConnectorHttpError = ConnectorHttpError(
            status_code=503, error_code="UPSTREAM", response_body="down"
        )
        assert isinstance(err, ConnectorError)

    def test_str_is_readable(self) -> None:
        """str() on ConnectorHttpError produces a readable message."""
        err: ConnectorHttpError = ConnectorHttpError(
            status_code=500,
            error_code="PTV_UPSTREAM_ERROR",
            response_body="Internal Server Error",
        )
        text: str = str(err)
        assert "PTV_UPSTREAM_ERROR" in text


class TestConnectorTimeoutError:
    """ConnectorTimeoutError tests."""

    def test_fields_assigned_correctly(self) -> None:
        """Constructor assigns path and attempts."""
        err: ConnectorTimeoutError = ConnectorTimeoutError(
            path="/v3/stops/location/-37.82,144.96",
            attempts=3,
        )
        assert err.path == "/v3/stops/location/-37.82,144.96"
        assert err.attempts == 3

    def test_is_instance_of_connector_error(self) -> None:
        """ConnectorTimeoutError is a subclass of ConnectorError."""
        err: ConnectorTimeoutError = ConnectorTimeoutError(path="/v3/test", attempts=3)
        assert isinstance(err, ConnectorError)

    def test_str_is_readable(self) -> None:
        """str() on ConnectorTimeoutError produces a readable message."""
        err: ConnectorTimeoutError = ConnectorTimeoutError(
            path="/v3/stops/location/-37.82,144.96",
            attempts=3,
        )
        text: str = str(err)
        assert "/v3/stops/location/-37.82,144.96" in text


# ============================================================================
# ConnectorConfig (Subtask 2)
# ============================================================================


class TestConnectorConfig:
    """ConnectorConfig frozen dataclass tests."""

    def test_default_values(self) -> None:
        """Only base_url is required; others have sensible defaults."""
        cfg: ConnectorConfig = ConnectorConfig(base_url="https://api.example.com")
        assert cfg.base_url == "https://api.example.com"
        assert cfg.default_timeout_secs == 5.0
        assert cfg.max_retries == 2
        assert cfg.retry_backoff_base_secs == 1.0

    def test_all_fields_custom(self) -> None:
        """All fields can be set explicitly."""
        cfg: ConnectorConfig = ConnectorConfig(
            base_url="https://custom.example.com",
            default_timeout_secs=10.0,
            max_retries=5,
            retry_backoff_base_secs=2.0,
        )
        assert cfg.base_url == "https://custom.example.com"
        assert cfg.default_timeout_secs == 10.0
        assert cfg.max_retries == 5
        assert cfg.retry_backoff_base_secs == 2.0

    def test_frozen_prevents_mutation(self) -> None:
        """ConnectorConfig is frozen — attribute assignment raises."""
        cfg: ConnectorConfig = ConnectorConfig(base_url="https://api.example.com")
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError or similar
            cfg.base_url = "https://evil.com"  # type: ignore[misc]


# ============================================================================
# BaseConnector (Subtask 2)
# ============================================================================


class TestBaseConnectorGetClient:
    """Tests for BaseConnector._get_client_async."""

    @pytest.mark.anyio
    async def test_lazy_initialisation(self) -> None:
        """_client starts as None; _get_client_async creates an AsyncClient."""
        connector: FakeConnector = _make_connector()
        assert connector._client is None
        client: httpx.AsyncClient = await connector._get_client_async()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        assert connector._client is client

    @pytest.mark.anyio
    async def test_returns_same_instance_on_second_call(self) -> None:
        """Subsequent calls return the same cached AsyncClient."""
        connector: FakeConnector = _make_connector()
        client1: httpx.AsyncClient = await connector._get_client_async()
        client2: httpx.AsyncClient = await connector._get_client_async()
        assert client1 is client2

    @pytest.mark.anyio
    async def test_base_url_from_config(self) -> None:
        """AsyncClient is created with base_url from ConnectorConfig."""
        connector: FakeConnector = _make_connector()
        client: httpx.AsyncClient = await connector._get_client_async()
        assert str(client.base_url) == "https://api.example.com"


class TestBaseConnectorRequestAsync:
    """Tests for BaseConnector._request_async covering all HTTP paths."""

    @pytest.mark.anyio
    async def test_2xx_returns_json(self) -> None:
        """Successful 2xx response returns the parsed JSON body."""
        connector: FakeConnector = _make_connector()
        connector._client = MagicMock(spec=httpx.AsyncClient)
        connector._client.build_request.return_value = httpx.Request(
            method="GET",
            url="https://api.example.com/v3/test",
        )
        expected: dict[str, object] = {"key": "value"}
        connector._client.send = AsyncMock(
            return_value=_make_mock_response(status_code=200, json_data=expected)
        )

        result: dict[str, object] = await connector._request_async("GET", "/v3/test")
        assert result == expected

    @pytest.mark.anyio
    async def test_4xx_raises_connector_http_error_with_mapped_code(self) -> None:
        """4xx → ConnectorHttpError with error_code from _map_error()."""
        connector: FakeConnector = _make_connector()
        connector._client = MagicMock(spec=httpx.AsyncClient)
        connector._client.build_request.return_value = httpx.Request(
            method="GET",
            url="https://api.example.com/v3/test",
        )
        connector._client.send = AsyncMock(
            return_value=_make_mock_response(
                status_code=429,
                text='{"error": "Too many requests"}',
            )
        )

        with pytest.raises(ConnectorHttpError) as exc_info:
            await connector._request_async("GET", "/v3/test")
        err: ConnectorHttpError = exc_info.value
        assert err.status_code == 429
        assert err.error_code == "FAKE_429"
        assert err.response_body == '{"error": "Too many requests"}'

    @pytest.mark.anyio
    async def test_5xx_raises_connector_http_error(self) -> None:
        """5xx → ConnectorHttpError (no retry on HTTP errors)."""
        connector: FakeConnector = _make_connector()
        connector._client = MagicMock(spec=httpx.AsyncClient)
        connector._client.build_request.return_value = httpx.Request(
            method="GET",
            url="https://api.example.com/v3/test",
        )
        connector._client.send = AsyncMock(
            return_value=_make_mock_response(
                status_code=503,
                text="Service Unavailable",
            )
        )

        with pytest.raises(ConnectorHttpError) as exc_info:
            await connector._request_async("GET", "/v3/test")
        err: ConnectorHttpError = exc_info.value
        assert err.status_code == 503
        assert err.error_code == "FAKE_503"

    @pytest.mark.anyio
    async def test_timeout_retry_succeeds(self) -> None:
        """First attempt times out, second attempt succeeds."""
        connector: FakeConnector = _make_connector()
        connector._client = MagicMock(spec=httpx.AsyncClient)
        connector._client.build_request.return_value = httpx.Request(
            method="GET",
            url="https://api.example.com/v3/test",
        )
        expected: dict[str, object] = {"recovered": True}
        connector._client.send = AsyncMock(
            side_effect=[
                httpx.TimeoutException("timed out"),
                _make_mock_response(status_code=200, json_data=expected),
            ]
        )

        # Patch asyncio.sleep to avoid real delay in tests.
        result: dict[str, object] = await connector._request_async("GET", "/v3/test")
        assert result == expected
        assert connector._client.send.call_count == 2

    @pytest.mark.anyio
    async def test_timeout_exhausted_raises_connector_timeout_error(self) -> None:
        """All retries time out → ConnectorTimeoutError."""
        config: ConnectorConfig = ConnectorConfig(
            base_url="https://api.example.com",
            max_retries=2,
            retry_backoff_base_secs=0.001,
        )
        connector: FakeConnector = FakeConnector(config=config)
        connector._client = MagicMock(spec=httpx.AsyncClient)
        connector._client.build_request.return_value = httpx.Request(
            method="GET",
            url="https://api.example.com/v3/stops",
        )
        connector._client.send = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        with pytest.raises(ConnectorTimeoutError) as exc_info:
            await connector._request_async("GET", "/v3/stops")
        err: ConnectorTimeoutError = exc_info.value
        assert err.path == "/v3/stops"
        assert err.attempts == 3  # 1 initial + 2 retries


class TestBaseConnectorClose:
    """Tests for BaseConnector.close_async."""

    @pytest.mark.anyio
    async def test_close_cleans_up_client(self) -> None:
        """close_async calls aclose on the underlying client and sets _client to None."""
        connector: FakeConnector = _make_connector()
        await connector._get_client_async()  # force initialisation
        assert connector._client is not None

        mock_close: AsyncMock = AsyncMock()
        connector._client.aclose = mock_close  # type: ignore[method-assign]

        await connector.close_async()
        mock_close.assert_awaited_once()
        assert connector._client is None

    @pytest.mark.anyio
    async def test_close_when_not_initialised_is_noop(self) -> None:
        """close_async when _client is None does not raise."""
        connector: FakeConnector = _make_connector()
        assert connector._client is None
        await connector.close_async()  # should not raise
        assert connector._client is None
