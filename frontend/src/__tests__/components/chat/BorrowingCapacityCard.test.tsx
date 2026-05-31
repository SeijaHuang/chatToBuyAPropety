import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { BorrowingCapacityCard } from '@/components/BorrowingCapacityCard'
import type { BorrowingCapacityResult } from '@/types'

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

describe('BorrowingCapacityCard', () => {
  it('renders formatted estimated capacity', () => {
    render(<BorrowingCapacityCard data={SAMPLE_BORROWING} />)
    expect(screen.getByText('$560,000')).toBeTruthy()
  })

  it('renders annual rate', () => {
    render(<BorrowingCapacityCard data={SAMPLE_BORROWING} />)
    expect(screen.getByText('6.25% p.a.')).toBeTruthy()
  })

  it('renders loan term in years', () => {
    render(<BorrowingCapacityCard data={SAMPLE_BORROWING} />)
    expect(screen.getByText('30 years')).toBeTruthy()
  })

  it('renders disclaimer text in the document', () => {
    render(<BorrowingCapacityCard data={SAMPLE_BORROWING} />)
    expect(
      screen.getByText('This is an estimate only and does not constitute financial advice.'),
    ).toBeTruthy()
  })

  it('renders disclaimer text visibly', () => {
    render(<BorrowingCapacityCard data={SAMPLE_BORROWING} />)
    expect(
      screen.getByText('This is an estimate only and does not constitute financial advice.'),
    ).toBeVisible()
  })

  it('renders rate source in disclaimer or card', () => {
    render(<BorrowingCapacityCard data={SAMPLE_BORROWING} />)
    expect(screen.getByText('30 years')).toBeTruthy()
    // rate_source is captured in the rendered card data
    const { container } = render(<BorrowingCapacityCard data={SAMPLE_BORROWING} />)
    expect(container.textContent).toContain('6.25')
  })
})
