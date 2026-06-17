'use client'

import { useEffect, useState } from 'react'
import { useConversationStore } from '@/stores/conversationStore'

interface UseSessionReturn {
  isRestored: boolean
}

export function useSession(sessionId: string): UseSessionReturn {
  const restoreFromStorage = useConversationStore((s) => s.restoreFromStorage)
  const initSession = useConversationStore((s) => s.initSession)
  const [isRestored, setIsRestored] = useState<boolean>(false)

  useEffect(() => {
    const restored: boolean = restoreFromStorage(sessionId)
    setIsRestored(restored)
    if (!restored) {
      initSession(sessionId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  return { isRestored }
}
