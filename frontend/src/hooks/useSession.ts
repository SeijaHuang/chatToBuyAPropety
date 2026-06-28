'use client'

import { useEffect, useState } from 'react'
import { useConversationStore } from '@/stores/conversationStore'
import { getSession } from '@/services/chat'

interface UseSessionReturn {
  isRestored: boolean
  isLoading: boolean
}

export function useSession(sessionId: string, enabled = true): UseSessionReturn {
  const initSession = useConversationStore((s) => s.initSession)
  const restoreSession = useConversationStore((s) => s.restoreSession)
  const [isRestored, setIsRestored] = useState<boolean>(false)
  const [isLoading, setIsLoading] = useState<boolean>(false)

  useEffect(() => {
    if (!enabled) return

    setIsLoading(true)

    async function loadSession(): Promise<void> {
      const response = await getSession(sessionId)
      if (response.ok) {
        restoreSession(response.data)
        setIsRestored(true)
      } else {
        initSession(sessionId)
        setIsRestored(false)
      }
      setIsLoading(false)
    }

    void loadSession()
  }, [sessionId, enabled, initSession, restoreSession])

  return { isRestored, isLoading: enabled && isLoading }
}
