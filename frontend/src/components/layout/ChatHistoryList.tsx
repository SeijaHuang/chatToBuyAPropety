'use client'

import React from 'react'
import { useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import { formatRelativeTime } from '@/lib/utils'
import { SkeletonText } from '@/components/shared'
import { useChatHistory } from '@/hooks'
import type { ChatSessionDTO } from '@/types'

const INTENT_LABELS: Record<string, string> = {
  recommend_suburbs: 'Suburb Recommendations',
  list_properties: 'Property Search',
  property_detail: 'Property Detail',
  compare_properties: 'Compare Properties',
  open_ended_query: 'Property Chat',
}

interface ChatHistoryListProps {
  activePath: string
}

export function ChatHistoryList({ activePath }: ChatHistoryListProps): React.ReactElement {
  const router = useRouter()
  const { sessions, isLoading } = useChatHistory()

  return (
    <div className={cn('flex flex-col', 'mt-md px-sm', 'flex-1 overflow-y-auto min-h-0')}>
      <p className="text-label-md text-outline px-sm mb-xs">Recent</p>

      {isLoading ? (
        <div className="flex flex-col gap-xs px-sm" aria-busy="true">
          <SkeletonText className="h-10" />
          <SkeletonText className="h-10" />
          <SkeletonText className="h-10" />
        </div>
      ) : sessions.length === 0 ? (
        <p className="text-caption text-outline px-sm">No conversations yet</p>
      ) : (
        <ul className="flex flex-col gap-xs" role="list">
          {sessions.map((session: ChatSessionDTO) => {
            const isActive: boolean = activePath === `/chat/${session.sessionId}`
            const label: string = session.initialIntent
              ? (INTENT_LABELS[session.initialIntent] ?? 'New Conversation')
              : 'New Conversation'

            return (
              <li key={session.sessionId}>
                <button
                  className={cn(
                    'flex flex-col w-full text-left',
                    'px-sm py-xs rounded-md',
                    'transition-colors',
                    isActive
                      ? 'bg-surface-container text-on-surface'
                      : 'text-on-surface-variant hover:bg-surface-variant'
                  )}
                  onClick={(): void => {
                    router.push(`/chat/${session.sessionId}`)
                  }}
                  aria-label={`Open conversation from ${formatRelativeTime(session.updatedAt)}`}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <span className="text-label-lg truncate">{label}</span>
                  <span className="text-caption text-outline">
                    {formatRelativeTime(session.updatedAt)}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
