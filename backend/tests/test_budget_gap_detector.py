"""Unit tests for domain/budget_gap_detector.py (S-H)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domain.budget_gap_detector import detect_budget_gap_async
from models.conversation_state import ConversationStateDTO
from models.financial import (
    ADJUST_PROPERTY_TYPE,
    EXPLORE_NEARBY_SUBURBS,
    BudgetGapResult,
)
from prompts.system_prompt_builder import build_question_prompt


def _mock_domain_response(median: int) -> MagicMock:
    """Return a mock httpx Response that yields the given median price."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"median": median}
    return resp


@pytest.mark.asyncio
async def test_gap_detected_when_over_15_percent() -> None:
    """Gap > 15 % produces has_gap=True with at least 2 suggested actions."""
    mock_resp = _mock_domain_response(700_000)
    mock_get = AsyncMock(return_value=mock_resp)

    with (
        patch("domain.budget_gap_detector.settings") as mock_settings,
        patch("domain.budget_gap_detector.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_settings.domain_api_key = "test-key"
        mock_settings.budget_gap_threshold = 0.15
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.get = mock_get
        mock_client_cls.return_value = mock_client_instance

        result = await detect_budget_gap_async(
            budget_max=500_000,
            property_type="house",
            min_bedrooms=3,
            suburbs=["Hawthorn"],
        )

    assert result is not None
    assert result.has_gap is True
    assert result.gap_percentage == pytest.approx(28.57, abs=0.1)
    assert len(result.suggested_actions) >= 2


@pytest.mark.asyncio
async def test_no_gap_within_threshold() -> None:
    """Gap < 15 % produces has_gap=False."""
    mock_resp = _mock_domain_response(700_000)
    mock_get = AsyncMock(return_value=mock_resp)

    with (
        patch("domain.budget_gap_detector.settings") as mock_settings,
        patch("domain.budget_gap_detector.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_settings.domain_api_key = "test-key"
        mock_settings.budget_gap_threshold = 0.15
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.get = mock_get
        mock_client_cls.return_value = mock_client_instance

        result = await detect_budget_gap_async(
            budget_max=680_000,
            property_type="house",
            min_bedrooms=3,
            suburbs=["Hawthorn"],
        )

    assert result is not None
    assert result.has_gap is False


@pytest.mark.asyncio
async def test_returns_none_when_api_fails() -> None:
    """A network error causes the function to return None silently."""
    import httpx

    with (
        patch("domain.budget_gap_detector.settings") as mock_settings,
        patch("domain.budget_gap_detector.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_settings.domain_api_key = "test-key"
        mock_settings.budget_gap_threshold = 0.15
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.get = AsyncMock(side_effect=httpx.RequestError("connection refused"))
        mock_client_cls.return_value = mock_client_instance

        result = await detect_budget_gap_async(
            budget_max=500_000,
            property_type="house",
            min_bedrooms=3,
            suburbs=["Hawthorn"],
        )

    assert result is None


@pytest.mark.asyncio
async def test_suggested_actions_minimum_count() -> None:
    """When has_gap is True, at least 2 suggested actions are returned."""
    mock_resp = _mock_domain_response(700_000)
    mock_get = AsyncMock(return_value=mock_resp)

    with (
        patch("domain.budget_gap_detector.settings") as mock_settings,
        patch("domain.budget_gap_detector.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_settings.domain_api_key = "test-key"
        mock_settings.budget_gap_threshold = 0.15
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.get = mock_get
        mock_client_cls.return_value = mock_client_instance

        result = await detect_budget_gap_async(
            budget_max=500_000,
            property_type="house",
            min_bedrooms=3,
            suburbs=["Hawthorn"],
        )

    assert result is not None
    assert result.has_gap is True
    assert len(result.suggested_actions) >= 2


def test_system_prompt_includes_gap_warning() -> None:
    """build_question_prompt injects the budget gap section when budget_gap is set."""
    state = ConversationStateDTO(session_id="test-session-gap")
    state.budget_gap = BudgetGapResult(
        has_gap=True,
        budget_max=500_000,
        market_median=700_000,
        gap_amount=200_000,
        gap_percentage=28.57,
        reference_suburb="Hawthorn",
        suggested_actions=(EXPLORE_NEARBY_SUBURBS, ADJUST_PROPERTY_TYPE),
    )
    prompt = build_question_prompt(state)
    assert "Budget Gap Detected" in prompt
