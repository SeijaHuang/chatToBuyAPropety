"""Financial result data classes for borrowing capacity and budget gap analysis."""

from dataclasses import dataclass


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
