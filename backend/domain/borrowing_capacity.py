"""Borrowing capacity estimation using RBA reference rates and a 28% DTI model."""

import csv
import io
from collections.abc import Iterator
from datetime import datetime

import httpx
import structlog

from config import settings
from models.conversation_state import M4Budget
from models.financial import BorrowingCapacityResult

logger = structlog.get_logger()

F5_CSV_URL = "https://www.rba.gov.au/statistics/tables/csv/f5-data.csv"
F5_TARGET_FIELD = "FILRHLBVD"
CACHE_TTL_SECONDS = 86_400

_rate_cache: tuple[float, str] | None = None
_cache_fetched_at: datetime | None = None


def _parse_f5_latest(csv_text: str, series_id: str) -> float:
    """Parse RBA F5 CSV and return the latest non-empty value for a series ID.

    Skips metadata header rows, locates the column by series_id, then scans
    data rows from the end to return the most recent non-empty value.

    Args:
        csv_text: Raw CSV content from the RBA F5 statistics file.
        series_id: The series identifier to locate (e.g. FILRHLBVD).

    Returns:
        The most recent non-empty float value for that series.

    Raises:
        ValueError: If the series ID is not found or no valid numeric data exists.
    """
    reader: Iterator[list[str]] = csv.reader(io.StringIO(csv_text))
    rows: list[list[str]] = list(reader)

    col_idx: int | None = None
    series_row_idx: int | None = None

    for i, row in enumerate(rows):
        if series_id in row:
            col_idx = row.index(series_id)
            series_row_idx = i
            break

    if col_idx is None or series_row_idx is None:
        raise ValueError(f"Series ID {series_id!r} not found in CSV headers")

    for row in reversed(rows[series_row_idx + 1 :]):
        if col_idx >= len(row):
            continue
        cell: str = row[col_idx].strip()
        if not cell:
            continue
        try:
            return float(cell)
        except ValueError:
            continue

    raise ValueError(f"No valid numeric data found for series {series_id!r}")


async def get_reference_rate_async() -> tuple[float, str]:
    """Return the current RBA variable rate and a source description string.

    Fetches the RBA F5 CSV on cache miss; returns the cached value within 24 hours.
    Falls back to settings.standard_variable_rate on any network or parse error
    without updating the cache so the next call retries the fetch.

    Returns:
        Tuple of (annual_rate_percent, source_description).
    """
    global _rate_cache, _cache_fetched_at

    now: datetime = datetime.now()
    if (
        _rate_cache is not None
        and _cache_fetched_at is not None
        and (now - _cache_fetched_at).total_seconds() < CACHE_TTL_SECONDS
    ):
        return _rate_cache

    rate: float
    rate_source: str
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(F5_CSV_URL, timeout=5.0)
            response.raise_for_status()
        rate = _parse_f5_latest(response.text, F5_TARGET_FIELD)
        rate_source = f"RBA F5 variable discounted owner-occupier rate {rate:.2f}% p.a."
        _rate_cache = (rate, rate_source)
        _cache_fetched_at = now
        logger.info("rba_rate_fetched", rate=rate)
        return _rate_cache
    except Exception:
        rate = settings.standard_variable_rate
        rate_source = f"Reference rate {rate:.2f}% p.a. (RBA F5 temporarily unavailable)"
        logger.warning("rba_rate_fetch_failed", fallback_rate=rate)
        return (rate, rate_source)


def _annuity_factor(annual_rate_pct: float, years: int) -> float:
    """Compute the standard equal-payment annuity factor.

    Args:
        annual_rate_pct: Annual interest rate as a percentage (e.g. 6.30 for 6.30%).
        years: Loan term in years.

    Returns:
        Present value of $1/month payments over the given term at the given rate.
    """
    r: float = annual_rate_pct / 100 / 12
    n: int = years * 12
    return (1 - (1 + r) ** -n) / r


async def estimate_borrowing_capacity_async(
    m4: M4Budget,
) -> BorrowingCapacityResult | None:
    """Estimate maximum borrowing capacity from M4 budget data.

    Uses a 28% DTI model applied to net monthly income (67% of pre-tax salary)
    and an annuity factor derived from the current RBA reference rate.

    Args:
        m4: The M4 budget sub-model with salary and loan preference fields.

    Returns:
        BorrowingCapacityResult with the capacity estimate and disclaimer,
        or None if pre_tax_salary has not been collected yet.
    """
    if m4.pre_tax_salary is None:
        return None

    annual_rate: float
    rate_source: str
    annual_rate, rate_source = await get_reference_rate_async()
    loan_term: int = (
        m4.loan_term_years if m4.loan_term_years is not None else settings.default_loan_term
    )

    net_monthly: float = m4.pre_tax_salary * 0.67 / 12
    if m4.is_joint is True and m4.partner_salary is not None:
        net_monthly += m4.partner_salary * 0.67 / 12

    max_monthly_repayment: float = net_monthly * settings.borrowing_capacity_dti
    raw_capacity: float = max_monthly_repayment * _annuity_factor(annual_rate, loan_term)
    estimated_capacity: int = round(raw_capacity / 10_000) * 10_000

    based_on_salary: int = m4.pre_tax_salary + (m4.partner_salary or 0)
    is_joint: bool = bool(m4.is_joint and m4.partner_salary is not None)

    disclaimer: str = (
        f"This borrowing capacity estimate is based on a {annual_rate:.2f}% p.a. "
        f"variable rate, {loan_term}-year loan term, and a "
        f"{settings.borrowing_capacity_dti:.0%} monthly income repayment limit. "
        f"Actual borrowing capacity varies by lender policy, existing debts, LVR, "
        f"and credit profile. Consult a licensed mortgage broker for an accurate assessment."
    )

    return BorrowingCapacityResult(
        estimated_capacity=estimated_capacity,
        monthly_repayment=int(max_monthly_repayment),
        based_on_salary=based_on_salary,
        is_joint=is_joint,
        annual_rate=annual_rate,
        loan_term_years=loan_term,
        rate_source=rate_source,
        disclaimer=disclaimer,
    )
