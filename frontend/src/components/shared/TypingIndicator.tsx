'use client'

import React from 'react'

const DELAYS = [0, 200, 400] as const

export function TypingIndicator(): React.ReactElement {
  return (
    <span
      role="status"
      aria-label="Assistant is typing"
      data-testid="typing-indicator"
      className="inline-flex items-center gap-1"
    >
      {DELAYS.map((delay) => (
        <span
          key={delay}
          style={{ animationDelay: `${delay}ms` }}
          className="animate-typing-dot bg-tertiary-container inline-block w-1.5 h-1.5 rounded-full"
        />
      ))}
    </span>
  )
}
