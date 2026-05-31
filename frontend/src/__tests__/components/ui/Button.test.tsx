import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { Button } from '@/components/ui/Button'

describe('Button', () => {
  it('renders with primary variant classes', () => {
    render(<Button variant="primary">Click</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('bg-primary-container')
  })

  it('renders with secondary variant classes', () => {
    render(<Button variant="secondary">Click</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('border-outline-variant')
  })

  it('renders with ghost variant classes', () => {
    render(<Button variant="ghost">Click</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('text-primary')
  })

  it('renders with danger variant classes', () => {
    render(<Button variant="danger">Click</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('bg-error-container')
  })

  it('is disabled when loading prop is true', () => {
    render(<Button loading>Click</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('does not call onClick when loading', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<Button loading onClick={onClick}>Click</Button>)
    await user.click(screen.getByRole('button'))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('does not call onClick when disabled', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<Button disabled onClick={onClick}>Click</Button>)
    await user.click(screen.getByRole('button'))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('renders icon when icon prop provided', () => {
    render(<Button icon="home">Click</Button>)
    expect(screen.getByText('home')).toBeTruthy()
  })

  it('renders sm size classes', () => {
    render(<Button size="sm">Click</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('h-sm')
  })

  it('renders md size classes', () => {
    render(<Button size="md">Click</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('h-md')
  })

  it('renders lg size classes', () => {
    render(<Button size="lg">Click</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('h-lg')
  })
})
