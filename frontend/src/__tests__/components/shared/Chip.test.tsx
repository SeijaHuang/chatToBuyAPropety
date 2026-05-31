import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { Chip } from '@/components/shared/Chip'

describe('Chip', () => {
  it('renders the label text', () => {
    render(<Chip label="Test label" />)
    expect(screen.getByText('Test label')).toBeTruthy()
  })

  it('shows remove button when onRemove is provided', () => {
    render(<Chip label="Tag" onRemove={vi.fn()} />)
    expect(screen.getByRole('button', { name: /remove tag/i })).toBeTruthy()
  })

  it('does not show remove button when onRemove absent', () => {
    render(<Chip label="Tag" />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('calls onRemove when remove button is clicked', async () => {
    const onRemove = vi.fn()
    const user = userEvent.setup()
    render(<Chip label="Tag" onRemove={onRemove} />)
    await user.click(screen.getByRole('button', { name: /remove tag/i }))
    expect(onRemove).toHaveBeenCalledOnce()
  })

  it('has rounded-full class on container', () => {
    const { container } = render(<Chip label="Tag" />)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('rounded-full')
  })
})
