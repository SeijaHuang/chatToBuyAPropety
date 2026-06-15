'use client'

import React, { useEffect, useRef } from 'react'
import { useConversationStore } from '@/stores/conversationStore'
import { useChat } from '@/hooks'
import { ChatInput } from '@/components/ChatInput'
import { ChatMessage } from '@/components/ChatMessage'
import { ModuleProgress } from '@/components/ModuleProgress'
import { cn } from '@/lib/utils'
import type { UIMessage, ConversationStateDTO } from '@/types'

interface ChatSessionProps {
  sessionId: string
}

export function ChatSession({ sessionId }: ChatSessionProps): React.ReactElement | null {
  const messages: UIMessage[] = useConversationStore((s) => s.messages)
  const isLoading: boolean = useConversationStore((s) => s.isLoading)
  const state: ConversationStateDTO | null = useConversationStore((s) => s.state)
  const restoreFromStorage = useConversationStore((s) => s.restoreFromStorage)
  const initSession = useConversationStore((s) => s.initSession)

  const { sendMessage } = useChat()
  const messageListRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const restored: boolean = restoreFromStorage(sessionId)
    if (!restored) {
      initSession(sessionId)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight
    }
  }, [messages])

  if (state === null) {
    return null
  }

  return (
    <div className={cn('flex flex-col', 'h-screen')}>
      <ModuleProgress
        completionStatus={state.completionStatus}
        currentModule={state.currentModule}
      />

      <div
        ref={messageListRef}
        className={cn(
          'flex-1 overflow-y-auto',
          'px-md py-lg',
          'flex flex-col gap-md',
        )}
      >
        {messages.map((msg: UIMessage) => (
          <ChatMessage
            key={msg.id}
            role={msg.role}
            content={msg.content}
            isLoading={msg.isLoading}
            borrowingCapacity={msg.borrowingCapacity}
            budgetGap={msg.budgetGap}
          />
        ))}
      </div>

      <div className={cn('sticky bottom-0', 'px-md py-sm', 'bg-surface')}>
        <ChatInput onSend={sendMessage} isLoading={isLoading} />
      </div>
    </div>
  )
}
