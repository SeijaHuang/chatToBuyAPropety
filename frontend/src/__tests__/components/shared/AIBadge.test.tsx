import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { AIBadge } from '@/components/shared/AIBadge'

describe('AIBadge', () => {
  it('renders the auto_awesome icon text', () => {
    render(<AIBadge />)
    expect(screen.getByText('auto_awesome')).toBeTruthy()
  })

  it('renders default label AI', () => {
    render(<AIBadge />)
    expect(screen.getByText('AI')).toBeTruthy()
  })

  it('renders custom label when provided', () => {
    render(<AIBadge label="Smart" />)
    expect(screen.getByText('Smart')).toBeTruthy()
  })
})
