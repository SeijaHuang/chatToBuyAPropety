import type { Story } from '@ladle/react'
import type { BorrowingCapacityResult } from '@/types'
import { BorrowingCapacityCard } from '@/components/BorrowingCapacityCard'

const SAMPLE_BORROWING: BorrowingCapacityResult = {
  estimated_capacity: 560000,
  monthly_repayment: 2340,
  based_on_salary: 120000,
  is_joint: false,
  annual_rate: 6.25,
  loan_term_years: 30,
  rate_source: 'RBA cash rate + 3% buffer',
  disclaimer: 'This is an estimate only and does not constitute financial advice.',
}

export const Default: Story = () => (
  <div className="p-md">
    <BorrowingCapacityCard data={SAMPLE_BORROWING} />
  </div>
)
