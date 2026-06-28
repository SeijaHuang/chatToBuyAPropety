'use client'

import React, { useRef, useEffect } from 'react'
import { useConversationStore } from '@/stores/conversationStore'
import { useUIStore } from '@/stores'
import { useChat } from '@/hooks/useChat'
import { useSession } from '@/hooks/useSession'
import { ChatInput } from '@/components/ChatInput'
import { ChatMessage } from '@/components/ChatMessage'
import { Button } from '@/components/shared'
import { cn } from '@/lib/utils'
import type { UIMessage, RoutingPayload } from '@/types'

interface ChatSessionProps {
  sessionId: string
  initialMessage?: string | null
}

export function ChatSession({ sessionId, initialMessage = null }: ChatSessionProps): React.ReactElement | null {
  const messages: UIMessage[] = useConversationStore((s) => s.messages)
  const isLoading: boolean = useConversationStore((s) => s.isLoading)
  const routing: RoutingPayload | null = useConversationStore((s) => s.routing)
  const sidebarCollapsed: boolean = useUIStore((s) => s.sidebarCollapsed)

  const isNewSession: boolean = sessionId === 'new'
  const clearSession = useConversationStore((s) => s.clearSession)
  const { sendMessage, errorMessage } = useChat()
  const { isLoading: sessionLoading } = useSession(sessionId, !isNewSession)

  const messageListRef = useRef<HTMLDivElement>(null)
  const initialMessageSent = useRef<boolean>(false)

  useEffect(() => {
    if (isNewSession) {
      clearSession()
    }
  }, [isNewSession, clearSession])

  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight
    }
  }, [messages])

  useEffect(() => {
    if (!isNewSession || initialMessage === null || initialMessageSent.current) return
    initialMessageSent.current = true
    void sendMessage(initialMessage)
  }, [isNewSession, initialMessage, sendMessage])

  const handleViewProperties = (): void => {
    // P2: router.push('/properties') — routing payload passed via router state
    alert('Coming soon — property search will be available in the next release.')
  }

  if (sessionLoading) {
    return null
  }

  return (
    <div id="chat-session" className={cn('flex flex-col', 'h-screen')}>
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
            id={`chat-message-${msg.id}`}
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
          'fixed bottom-16 md:bottom-0 right-0 left-0',
          sidebarCollapsed ? 'md:left-sidebar-collapsed' : 'md:left-sidebar-expanded',
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
