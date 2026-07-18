"""Tests for agent.shared.connector — ConnectorError exception hierarchy.

BaseConnector + ConnectorConfig tests will be added in Subtask 2.
"""

from agent.shared.connector import (
    ConnectorError,
    ConnectorHttpError,
    ConnectorTimeoutError,
)
from exceptions import PropertyAIException


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
