import type { Story } from '@ladle/react'
import { BudgetGapCard } from '@/components/chat/BudgetGapCard'
import type { BudgetGapResult } from '@/types'

const SAMPLE_WITH_GAP: BudgetGapResult = {
  has_gap: true,
  budget_max: 600000,
  market_median: 850000,
  gap_amount: 250000,
  gap_percentage: 29.4,
  reference_suburb: 'Fitzroy',
  suggested_actions: ['Consider outer suburbs', 'Explore shared equity schemes'],
}

const SAMPLE_NO_GAP: BudgetGapResult = {
  has_gap: false,
  budget_max: 900000,
  market_median: 850000,
  gap_amount: 0,
  gap_percentage: 0,
  reference_suburb: 'Fitzroy',
  suggested_actions: [],
}

export const WithGap: Story = () => (
  <div className="p-md">
    <BudgetGapCard data={SAMPLE_WITH_GAP} />
  </div>
)

export const NoGap: Story = () => (
  <div className="p-md">
    <p className="text-body-md text-on-surface-variant mb-sm">
      (BudgetGapCard renders nothing when has_gap is false)
    </p>
    <BudgetGapCard data={SAMPLE_NO_GAP} />
  </div>
)
