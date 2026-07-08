import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ChatMessage } from '@/components/chat/ChatMessage'
import type { BorrowingCapacityResult, BudgetGapResult } from '@/types'

const SAMPLE_BORROWING: BorrowingCapacityResult = {
  estimated_capacity: 560000,
  monthly_repayment:  2340,
  based_on_salary:    120000,
  is_joint:           false,
  annual_rate:        6.25,
  loan_term_years:    30,
  rate_source:        'RBA cash rate + 3% buffer',
  disclaimer:         'This is an estimate only and does not constitute financial advice.',
}

const SAMPLE_BUDGET_GAP: BudgetGapResult = {
  has_gap:           true,
  budget_max:        600000,
  market_median:     850000,
  gap_amount:        250000,
  gap_percentage:    29.4,
  reference_suburb:  'Fitzroy',
  suggested_actions: ['Consider outer suburbs', 'Explore shared equity schemes'],
}

describe('ChatMessage', () => {
  it('renders the message content text', () => {
    render(<ChatMessage role="assistant" content="Hello from assistant" />)
    expect(screen.getByText('Hello from assistant')).toBeInTheDocument()
  })

  it('applies right-alignment class for user role', () => {
    const { container } = render(<ChatMessage role="user" content="Hello" />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toContain('items-end')
  })

  it('contains auto_awesome icon text for assistant role', () => {
    render(<ChatMessage role="assistant" content="Hi there" />)
    expect(screen.getByText('auto_awesome')).toBeTruthy()
  })

  it('renders TypingIndicator when isLoading is true', () => {
    render(<ChatMessage role="assistant" content="" isLoading={true} />)
    expect(screen.getByTestId('typing-indicator')).toBeTruthy()
  })

  it('does not render content text when isLoading is true', () => {
    render(<ChatMessage role="assistant" content="This should not appear" isLoading={true} />)
    expect(screen.queryByText('This should not appear')).toBeNull()
  })

  it('renders BorrowingCapacityCard when borrowingCapacity is provided', () => {
    render(
      <ChatMessage
        role="assistant"
        content="Here is your estimate:"
        borrowingCapacity={SAMPLE_BORROWING}
      />,
    )
    expect(screen.getByText('Borrowing Estimate')).toBeTruthy()
  })

  it('renders BudgetGapCard when budgetGap is provided', () => {
    render(
      <ChatMessage
        role="assistant"
        content="I noticed a gap:"
        budgetGap={SAMPLE_BUDGET_GAP}
      />,
    )
    expect(screen.getByText('Budget Gap Detected')).toBeTruthy()
  })
})
