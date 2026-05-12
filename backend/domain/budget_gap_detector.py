"""Budget gap detection service — compares user budget against Domain API market median."""

import httpx
import structlog

from config import settings
from models.financial import (
    ADJUST_PROPERTY_TYPE,
    EXPLORE_NEARBY_SUBURBS,
    REVISIT_BUDGET,
    BudgetGapResult,
)

logger = structlog.get_logger()

DOMAIN_PRICE_ESTIMATE_URL = "https://api.domain.com.au/v1/suburbs/{suburb}/price-estimate"
DOMAIN_MEDIAN_FIELD = "median"


async def detect_budget_gap_async(
    budget_max: int,
    property_type: str | None,
    min_bedrooms: int | None,
    suburbs: list[str],
) -> BudgetGapResult | None:
    """Detect whether the user's budget falls significantly below the market median.

    Calls the Domain API to retrieve the median price for the first suburb in the list,
    then computes the gap relative to budget_max. Returns None on any failure so the
    caller's main flow is never blocked.

    Args:
        budget_max: The user's stated maximum budget in AUD.
        property_type: Optional property category (e.g. "house", "unit").
        min_bedrooms: Optional minimum bedroom count for the query.
        suburbs: Non-empty list of suburbs; the first entry is used as the reference.

    Returns:
        BudgetGapResult when the API call succeeds, None otherwise.
    """
    if not settings.domain_api_key:
        return None

    reference_suburb = suburbs[0]

    params: dict[str, str] = {}
    if property_type is not None:
        params["propertyCategory"] = property_type
    if min_bedrooms is not None:
        params["bedrooms"] = str(min_bedrooms)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                DOMAIN_PRICE_ESTIMATE_URL.format(suburb=reference_suburb),
                params=params,
                headers={"Authorization": f"Bearer {settings.domain_api_key}"},
            )
            response.raise_for_status()
            data = response.json()
            market_median = int(data[DOMAIN_MEDIAN_FIELD])
    except Exception as e:
        logger.warning("budget_gap_detection_failed", error=str(e))
        return None

    gap_amount = market_median - budget_max
    gap_percentage = gap_amount / market_median * 100
    threshold_pct = settings.budget_gap_threshold * 100

    if gap_percentage > threshold_pct:
        has_gap = True
        actions: tuple[str, ...] = (EXPLORE_NEARBY_SUBURBS, ADJUST_PROPERTY_TYPE)
        if gap_percentage > 30.0:
            actions = (EXPLORE_NEARBY_SUBURBS, ADJUST_PROPERTY_TYPE, REVISIT_BUDGET)
    else:
        has_gap = False
        actions = ()

    return BudgetGapResult(
        has_gap=has_gap,
        budget_max=budget_max,
        market_median=market_median,
        gap_amount=gap_amount,
        gap_percentage=gap_percentage,
        reference_suburb=reference_suburb,
        suggested_actions=actions,
    )
