import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { ChatInput } from '@/components/ChatInput'

describe('ChatInput', () => {
  it('calls onSend with trimmed message on Enter', async () => {
    const onSend = vi.fn()
    const user = userEvent.setup()
    render(<ChatInput onSend={onSend} isLoading={false} />)
    await user.type(screen.getByRole('textbox'), '  hello world  ')
    await user.keyboard('{Enter}')
    expect(onSend).toHaveBeenCalledOnce()
    expect(onSend).toHaveBeenCalledWith('hello world')
  })

  it('does not call onSend on Shift+Enter', async () => {
    const onSend = vi.fn()
    const user = userEvent.setup()
    render(<ChatInput onSend={onSend} isLoading={false} />)
    await user.type(screen.getByRole('textbox'), 'hello')
    await user.keyboard('{Shift>}{Enter}{/Shift}')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('does not call onSend when message is empty after trim', async () => {
    const onSend = vi.fn()
    const user = userEvent.setup()
    render(<ChatInput onSend={onSend} isLoading={false} />)
    await user.type(screen.getByRole('textbox'), '   ')
    await user.keyboard('{Enter}')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('clears textarea after sending', async () => {
    const onSend = vi.fn()
    const user = userEvent.setup()
    render(<ChatInput onSend={onSend} isLoading={false} />)
    const textarea = screen.getByRole('textbox')
    await user.type(textarea, 'hello')
    await user.keyboard('{Enter}')
    expect(textarea).toHaveValue('')
  })

  it('disables textarea when isLoading is true', () => {
    render(<ChatInput onSend={vi.fn()} isLoading={true} />)
    expect(screen.getByRole('textbox')).toBeDisabled()
  })

  it('disables send button when isLoading is true', () => {
    render(<ChatInput onSend={vi.fn()} isLoading={true} />)
    expect(screen.getByRole('button', { name: /send message/i })).toBeDisabled()
  })

  it('enables textarea when isLoading is false', () => {
    render(<ChatInput onSend={vi.fn()} isLoading={false} />)
    expect(screen.getByRole('textbox')).not.toBeDisabled()
  })

  it('renders default placeholder when none provided', () => {
    render(<ChatInput onSend={vi.fn()} isLoading={false} />)
    expect(screen.getByRole('textbox')).toHaveAttribute(
      'placeholder',
      'Ask about your property needs…',
    )
  })

  it('renders custom placeholder when provided', () => {
    render(<ChatInput onSend={vi.fn()} isLoading={false} placeholder="Type here" />)
    expect(screen.getByRole('textbox')).toHaveAttribute('placeholder', 'Type here')
  })
})
