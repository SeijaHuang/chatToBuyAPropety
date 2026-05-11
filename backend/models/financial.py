"""Financial result data classes for borrowing capacity and budget gap analysis."""

from dataclasses import dataclass

EXPLORE_NEARBY_SUBURBS = "explore_nearby_suburbs"
ADJUST_PROPERTY_TYPE = "adjust_property_type"
REVISIT_BUDGET = "revisit_budget"


@dataclass(frozen=True)
class BorrowingCapacityResult:
    """Immutable result of a borrowing capacity estimation.

    Attributes:
        estimated_capacity: Estimated maximum borrowing amount in AUD, rounded to nearest $10,000.
        monthly_repayment: Monthly repayment ceiling in AUD (28% DTI of net monthly income).
        based_on_salary: Combined pre-tax salary used in the calculation (single or joint).
        is_joint: True when both pre_tax_salary and partner_salary contributed.
        annual_rate: Annual interest rate (%) used in the calculation.
        loan_term_years: Loan term in years used in the calculation.
        rate_source: Human-readable description of the rate source.
        disclaimer: Regulatory disclaimer to accompany any display of this estimate.
    """

    estimated_capacity: int
    monthly_repayment: int
    based_on_salary: int
    is_joint: bool
    annual_rate: float
    loan_term_years: int
    rate_source: str
    disclaimer: str


@dataclass(frozen=True)
class BudgetGapResult:
    """Immutable result of a budget gap analysis against market median price.

    Attributes:
        has_gap: True when the gap percentage exceeds the configured threshold.
        budget_max: User's stated maximum budget in AUD.
        market_median: Market median price for the reference suburb in AUD.
        gap_amount: Difference (market_median - budget_max); positive means underfunded.
        gap_percentage: gap_amount / market_median * 100.
        reference_suburb: The suburb used for the Domain API price query.
        suggested_actions: Recommended actions for the user (at least 2 when has_gap is True).
    """

    has_gap: bool
    budget_max: int
    market_median: int
    gap_amount: int
    gap_percentage: float
    reference_suburb: str
    suggested_actions: tuple[str, ...]
