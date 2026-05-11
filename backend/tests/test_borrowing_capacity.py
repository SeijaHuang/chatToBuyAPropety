"""Tests for services/borrowing_capacity.py — Story S-G."""

from unittest.mock import AsyncMock, patch

from config import settings
from models.conversation_state import M4Budget
from services.borrowing_capacity import estimate_borrowing_capacity_async

_MOCK_RATE: tuple[float, str] = (6.30, "RBA F5 rate 6.30% p.a.")
_PATCH_TARGET = "services.borrowing_capacity.get_reference_rate_async"


async def test_single_income_calculation() -> None:
    m4 = M4Budget(pre_tax_salary=100_000, is_joint=False)
    with patch(_PATCH_TARGET, new_callable=AsyncMock, return_value=_MOCK_RATE):
        result = await estimate_borrowing_capacity_async(m4)
    assert result is not None
    assert 230_000 <= result.estimated_capacity <= 270_000


async def test_joint_income_calculation() -> None:
    m4 = M4Budget(pre_tax_salary=100_000, is_joint=True, partner_salary=100_000)
    single_m4 = M4Budget(pre_tax_salary=100_000, is_joint=False)
    with patch(_PATCH_TARGET, new_callable=AsyncMock, return_value=_MOCK_RATE):
        result = await estimate_borrowing_capacity_async(m4)
        single_result = await estimate_borrowing_capacity_async(single_m4)
    assert result is not None
    assert single_result is not None
    assert result.estimated_capacity >= single_result.estimated_capacity * 1.8


async def test_returns_none_when_salary_is_none() -> None:
    m4 = M4Budget()
    with patch(_PATCH_TARGET, new_callable=AsyncMock, return_value=_MOCK_RATE):
        result = await estimate_borrowing_capacity_async(m4)
    assert result is None


async def test_disclaimer_contains_rate_and_term() -> None:
    m4 = M4Budget(pre_tax_salary=100_000)
    with patch(_PATCH_TARGET, new_callable=AsyncMock, return_value=_MOCK_RATE):
        result = await estimate_borrowing_capacity_async(m4)
    assert result is not None
    assert "6.30" in result.disclaimer
    assert "30" in result.disclaimer


async def test_capacity_rounded_to_nearest_ten_thousand() -> None:
    m4 = M4Budget(pre_tax_salary=100_000)
    with patch(_PATCH_TARGET, new_callable=AsyncMock, return_value=_MOCK_RATE):
        result = await estimate_borrowing_capacity_async(m4)
    assert result is not None
    assert result.estimated_capacity % 10_000 == 0


async def test_rba_fetch_failure_returns_fallback_result() -> None:
    m4 = M4Budget(pre_tax_salary=100_000)
    fallback_rate = settings.standard_variable_rate
    fallback_source = f"Reference rate {fallback_rate:.2f}% p.a. (RBA F5 temporarily unavailable)"
    with patch(
        _PATCH_TARGET, new_callable=AsyncMock, return_value=(fallback_rate, fallback_source)
    ):
        result = await estimate_borrowing_capacity_async(m4)
    assert result is not None
    assert "unavailable" in result.rate_source


async def test_shorter_loan_term_produces_lower_capacity() -> None:
    m4_25 = M4Budget(pre_tax_salary=100_000, loan_term_years=25)
    m4_30 = M4Budget(pre_tax_salary=100_000, loan_term_years=30)
    with patch(_PATCH_TARGET, new_callable=AsyncMock, return_value=_MOCK_RATE):
        result_25 = await estimate_borrowing_capacity_async(m4_25)
        result_30 = await estimate_borrowing_capacity_async(m4_30)
    assert result_25 is not None
    assert result_30 is not None
    assert result_25.estimated_capacity < result_30.estimated_capacity
