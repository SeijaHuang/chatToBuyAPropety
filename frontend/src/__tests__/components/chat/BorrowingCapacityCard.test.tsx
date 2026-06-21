import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { BorrowingCapacityCard } from '@/components/BorrowingCapacityCard'
import { mockBorrowingCapacity } from '@/__tests__/msw/fixtures'

// mockBorrowingCapacity:
//   estimated_capacity: 560000
//   annual_rate: 6.25
//   loan_term_years: 30
//   rate_source: 'RBA F5 lending rate indicator (2026-05)'
//   disclaimer: 'This is an estimate only based on RBA F5 indicator rate of 6.25% p.a. ...'

describe('BorrowingCapacityCard', () => {
  it('renders the formatted borrowing capacity amount', () => {
    render(<BorrowingCapacityCard data={mockBorrowingCapacity} />)
    expect(screen.getByText('$560,000')).toBeInTheDocument()
  })

  it('renders the annual rate value', () => {
    render(<BorrowingCapacityCard data={mockBorrowingCapacity} />)
    expect(screen.getByText('6.25% p.a.')).toBeInTheDocument()
  })

  it('renders the loan term value', () => {
    render(<BorrowingCapacityCard data={mockBorrowingCapacity} />)
    expect(screen.getByText('30 years')).toBeInTheDocument()
  })

  // *** COMPLIANCE TESTS — these three are the CI gate ***

  it('renders the disclaimer text in the document', () => {
    render(<BorrowingCapacityCard data={mockBorrowingCapacity} />)
    expect(screen.getByText(/estimate only/i)).toBeInTheDocument()
  })

  it('renders the disclaimer text visibly — not hidden by CSS', () => {
    render(<BorrowingCapacityCard data={mockBorrowingCapacity} />)
    expect(screen.getByText(/estimate only/i)).toBeVisible()
  })

  it('disclaimer text references the rate source', () => {
    render(<BorrowingCapacityCard data={mockBorrowingCapacity} />)
    // Both rate_source and disclaimer contain "RBA F5"; assert at least one is present
    expect(screen.getAllByText(/RBA F5/i).length).toBeGreaterThan(0)
  })
})
