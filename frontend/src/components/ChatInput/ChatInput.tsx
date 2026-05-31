'use client'

import { useState, useRef } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/shared'

interface ChatInputProps {
  onSend: (message: string) => void
  isLoading: boolean
  disabled?: boolean
  placeholder?: string
}

export function ChatInput({
  onSend,
  isLoading,
  disabled = false,
  placeholder = 'Ask about your property needs…',
}: ChatInputProps): React.ReactElement {
  const [value, setValue] = useState<string>('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const resizeTextarea = (el: HTMLTextAreaElement): void => {
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
    setValue(e.target.value)
    resizeTextarea(e.target)
  }

  const handleSend = (): void => {
    const trimmed: string = value.trim()
    if (!trimmed) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = '56px'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isDisabled: boolean = isLoading || disabled

  return (
    <div className={cn('glass-ai rounded-3xl', 'px-md py-sm')}>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        disabled={isDisabled}
        placeholder={placeholder}
        rows={1}
        aria-label="Message input"
        style={{ minHeight: '56px', maxHeight: '160px', overflowY: 'auto', resize: 'none' }}
        className={cn(
          'block w-full bg-transparent',
          'text-body-lg text-on-surface',
          'placeholder:text-on-surface-variant',
          'focus:outline-none',
          isDisabled && 'opacity-50 cursor-not-allowed'
        )}
      />
      <div className={cn('flex items-center justify-end', 'mt-xs')}>
        <Button
          type="button"
          variant="primary"
          icon="send"
          aria-label="Send message"
          onClick={handleSend}
          disabled={isDisabled}
          className="h-auto p-xs"
        />
      </div>
    </div>
  )
}
