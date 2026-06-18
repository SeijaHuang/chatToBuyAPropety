'use client'

import React from 'react'
import { cn } from '@/lib/utils'
import { MaterialSymbol, TypingIndicator } from '@/components/shared'
import { MESSAGE_ROLE } from '@/constants'
import { BorrowingCapacityCard } from '../BorrowingCapacityCard'
import { BudgetGapCard } from '../BudgetGapCard'
import type { MessageRole, BorrowingCapacityResult, BudgetGapResult } from '@/types'

interface ChatMessageProps {
  id?: string
  role: MessageRole
  content: string
  isLoading?: boolean
  timestamp?: Date
  borrowingCapacity?: BorrowingCapacityResult
  budgetGap?: BudgetGapResult
}

export function ChatMessage({
  id,
  role,
  content,
  isLoading = false,
  borrowingCapacity,
  budgetGap,
}: ChatMessageProps): React.ReactElement {
  const isUser: boolean = role === MESSAGE_ROLE.USER

  return (
    <div
      id={id}
      className={cn(
        'flex flex-col',
        'gap-sm',
        isUser ? 'items-end' : 'items-start',
      )}
    >
      <div className={cn('flex items-center', 'gap-sm')}>
        {!isUser && !isLoading && (
          <MaterialSymbol
            name="auto_awesome"
            filled
            className="text-tertiary-container mt-xs shrink-0"
          />
        )}
        <div
          className={cn(
            'rounded-2xl',
            'px-md py-sm',
            'text-body-lg text-on-surface',
            'max-w-prose',
            isUser ? 'bg-surface-container-high rounded-br-md' : '',
          )}
        >
          {isLoading ? <TypingIndicator /> : content}
        </div>
      </div>

      {borrowingCapacity != null && (
        <BorrowingCapacityCard data={borrowingCapacity} />
      )}
      {budgetGap != null && (
        <BudgetGapCard data={budgetGap} />
      )}
    </div>
  )
}
