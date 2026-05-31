import type { Story } from '@ladle/react'
import { ChatMessage } from '@/components/ChatMessage'
import type { BorrowingCapacityResult, BudgetGapResult } from '@/types'

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

const SAMPLE_BUDGET_GAP: BudgetGapResult = {
  has_gap: true,
  budget_max: 600000,
  market_median: 850000,
  gap_amount: 250000,
  gap_percentage: 29.4,
  reference_suburb: 'Fitzroy',
  suggested_actions: ['Consider outer suburbs', 'Explore shared equity schemes'],
}

export const UserMessage: Story = () => (
  <div className="p-md max-w-2xl">
    <ChatMessage role="user" content="I'm looking for a 3 bedroom house in Melbourne." />
  </div>
)

export const AssistantMessage: Story = () => (
  <div className="p-md max-w-2xl">
    <ChatMessage
      role="assistant"
      content="Great! I can help you find the perfect property. Could you tell me more about your lifestyle and commute needs?"
    />
  </div>
)

export const AssistantLoading: Story = () => (
  <div className="p-md max-w-2xl">
    <ChatMessage role="assistant" content="" isLoading={true} />
  </div>
)

export const WithBorrowingCapacity: Story = () => (
  <div className="p-md max-w-2xl">
    <ChatMessage
      role="assistant"
      content="Based on your salary, here's your estimated borrowing capacity:"
      borrowingCapacity={SAMPLE_BORROWING}
    />
  </div>
)

export const WithBudgetGap: Story = () => (
  <div className="p-md max-w-2xl">
    <ChatMessage
      role="assistant"
      content="I noticed a potential budget gap for your target suburb:"
      budgetGap={SAMPLE_BUDGET_GAP}
    />
  </div>
)
