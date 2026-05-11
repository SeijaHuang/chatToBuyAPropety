"""Financial estimate section builder for borrowing capacity context."""

from models.financial import BorrowingCapacityResult


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
