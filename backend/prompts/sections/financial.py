"""Financial estimate section builders for borrowing capacity and budget gap context."""

from models.shared.financial import BorrowingCapacityResult, BudgetGapResult


def build_borrowing_capacity_section(result: BorrowingCapacityResult | None) -> str:
    """Return a formatted borrowing capacity context block, or an empty string.

    Args:
        result: The borrowing capacity estimate, or None if not yet computed.

    Returns:
        Multi-line section string when result is available, empty string otherwise.
    """
    if result is None:
        return ""
    return (
        f"Borrowing Capacity Estimate:\n"
        f"  Estimated capacity: ${result.estimated_capacity:,}\n"
        f"  Monthly repayment limit: ${result.monthly_repayment:,}/month\n"
        f"  Based on salary: ${result.based_on_salary:,} "
        f"({'joint' if result.is_joint else 'single'})\n"
        f"  Rate: {result.annual_rate:.2f}% p.a. | Term: {result.loan_term_years} years\n"
        f"  Disclaimer: {result.disclaimer}"
    )


def build_budget_gap_section(result: BudgetGapResult | None) -> str:
    """Return budget gap warning string for injection into system prompt, or empty string.

    Args:
        result: The budget gap analysis result, or None if not yet computed.

    Returns:
        Multi-line warning section when a gap exists, empty string otherwise.
    """
    if result is None or not result.has_gap:
        return ""
    actions: str = ", ".join(result.suggested_actions)
    return (
        f"⚠ Budget Gap Detected:\n"
        f"  User budget: ${result.budget_max:,}\n"
        f"  Market median ({result.reference_suburb}): ${result.market_median:,}\n"
        f"  Gap: ${result.gap_amount:,} ({result.gap_percentage:.0f}%)\n"
        f"  Suggested actions: {actions}\n"
        f"  Action required: Flag this gap directly and kindly. "
        f"Suggest alternatives per Rule 3."
    )
