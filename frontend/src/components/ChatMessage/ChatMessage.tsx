'use client'

import { cn } from '@/lib/utils'
import { MaterialSymbol, TypingIndicator } from '@/components/shared'
import { MESSAGE_ROLE } from '@/constants'
import { BorrowingCapacityCard } from '../BorrowingCapacityCard'
import { BudgetGapCard } from '../BudgetGapCard'
import type { MessageRole, BorrowingCapacityResult, BudgetGapResult } from '@/types'

interface ChatMessageProps {
  role: MessageRole
  content: string
  isLoading?: boolean
  timestamp?: Date
  borrowingCapacity?: BorrowingCapacityResult
  budgetGap?: BudgetGapResult
}

export function ChatMessage({
  role,
  content,
  isLoading = false,
  borrowingCapacity,
  budgetGap,
}: ChatMessageProps): React.ReactElement {
  const isUser: boolean = role === MESSAGE_ROLE.USER

  return (
    <div
      className={cn(
        'flex flex-col',
        'gap-sm',
        isUser ? 'items-end' : 'items-start',
      )}
    >
      <div className={cn('flex items-start', 'gap-sm')}>
        {!isUser && (
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
