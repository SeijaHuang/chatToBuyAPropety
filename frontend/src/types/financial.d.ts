export interface BorrowingCapacityResult {
  estimated_capacity: number
  monthly_repayment:  number
  based_on_salary:    number
  is_joint:           boolean
  annual_rate:        number
  loan_term_years:    number
  rate_source:        string
  disclaimer:         string
}

export interface BudgetGapResult {
  has_gap:           boolean
  budget_max:        number
  market_median:     number
  gap_amount:        number
  gap_percentage:    number
  reference_suburb:  string
  suggested_actions: string[]
}
