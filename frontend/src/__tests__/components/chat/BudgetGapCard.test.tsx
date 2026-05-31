import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { BudgetGapCard } from '@/components/chat/BudgetGapCard'
import type { BudgetGapResult } from '@/types'

const SAMPLE_WITH_GAP: BudgetGapResult = {
  has_gap:           true,
  budget_max:        600000,
  market_median:     850000,
  gap_amount:        250000,
  gap_percentage:    29.4,
  reference_suburb:  'Fitzroy',
  suggested_actions: ['Consider outer suburbs', 'Explore shared equity schemes'],
}

const SAMPLE_NO_GAP: BudgetGapResult = {
  has_gap:           false,
  budget_max:        900000,
  market_median:     850000,
  gap_amount:        0,
  gap_percentage:    0,
  reference_suburb:  'Fitzroy',
  suggested_actions: [],
}

describe('BudgetGapCard', () => {
  it('renders nothing when has_gap is false', () => {
    const { container } = render(<BudgetGapCard data={SAMPLE_NO_GAP} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders gap percentage when has_gap is true', () => {
    render(<BudgetGapCard data={SAMPLE_WITH_GAP} />)
    expect(screen.getByText(/29\.4%/)).toBeTruthy()
  })

  it('renders reference suburb when has_gap is true', () => {
    render(<BudgetGapCard data={SAMPLE_WITH_GAP} />)
    expect(screen.getByText(/Fitzroy/)).toBeTruthy()
  })

  it('renders all suggested actions as chips when has_gap is true', () => {
    render(<BudgetGapCard data={SAMPLE_WITH_GAP} />)
    expect(screen.getByText('Consider outer suburbs')).toBeTruthy()
    expect(screen.getByText('Explore shared equity schemes')).toBeTruthy()
  })
})
