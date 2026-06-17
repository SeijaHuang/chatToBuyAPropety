'use client'

import React, { useRef, useEffect } from 'react'
import { useConversationStore } from '@/stores/conversationStore'
import { useChat } from '@/hooks/useChat'
import { useSession } from '@/hooks/useSession'
import { ChatInput } from '@/components/ChatInput'
import { ChatMessage } from '@/components/ChatMessage'
import { ModuleProgress } from '@/components/ModuleProgress'
import { Button } from '@/components/shared'
import { cn } from '@/lib/utils'
import { STORAGE_KEY } from '@/constants/storageKeys'
import type { UIMessage, ConversationStateDTO, RoutingPayload } from '@/types'

interface ChatSessionProps {
  sessionId: string
}

export function ChatSession({ sessionId }: ChatSessionProps): React.ReactElement | null {
  const messages: UIMessage[] = useConversationStore((s) => s.messages)
  const isLoading: boolean = useConversationStore((s) => s.isLoading)
  const state: ConversationStateDTO | null = useConversationStore((s) => s.state)
  const routing: RoutingPayload | null = useConversationStore((s) => s.routing)

  const { sendMessage, errorMessage } = useChat()
  useSession(sessionId)

  const messageListRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight
    }
  }, [messages])

  const handleViewProperties = (): void => {
    if (routing !== null) {
      sessionStorage.setItem(
        STORAGE_KEY.ROUTING_PAYLOAD_PREFIX + sessionId,
        JSON.stringify(routing)
      )
    }
    // P2: router.push('/properties')
    alert('Coming soon — property search will be available in the next release.')
  }

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
          'px-md py-lg pb-32',
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

        {routing !== null && (
          <div
            className={cn(
              'glass-ai',
              'rounded-xl p-md mx-md',
              'flex flex-col gap-sm',
            )}
          >
            <p className="text-body-md text-on-surface">
              {"I've collected everything I need. Ready to find properties?"}
            </p>
            <Button variant="primary" onClick={handleViewProperties}>
              View Matching Properties
            </Button>
          </div>
        )}
      </div>

      <div
        className={cn(
          'fixed bottom-0 left-0 right-0',
          'px-md py-sm',
          'bg-surface/80 backdrop-blur-glass',
          'flex flex-col gap-xs',
        )}
      >
        {errorMessage !== null && (
          <p
            role="alert"
            className={cn('text-label-md text-error text-center')}
          >
            {errorMessage}
          </p>
        )}
        <ChatInput onSend={sendMessage} isLoading={isLoading} />
        <p className="text-caption text-outline text-center">
          Homi AI can make mistakes. Verify important property or financial information.
        </p>
      </div>
    </div>
  )
}
