'use client'

import { useState, useEffect } from 'react'
import { getChats } from '@/services'
import type { ChatSessionDTO } from '@/types'

interface UseChatHistoryReturn {
  sessions: ChatSessionDTO[]
  isLoading: boolean
}

export function useChatHistory(): UseChatHistoryReturn {
  const [sessions, setSessions] = useState<ChatSessionDTO[]>([])
  const [isLoading, setIsLoading] = useState<boolean>(true)

  useEffect((): (() => void) => {
    let cancelled: boolean = false

    async function fetchChats(): Promise<void> {
      const response = await getChats()
      if (cancelled) return

      if (response.ok) {
        setSessions(response.data.slice(0, 10))
      }
      // 400 (missing cookie) or network error: silently show empty state
      setIsLoading(false)
    }

    void fetchChats()
    return (): void => {
      cancelled = true
    }
  }, [])

  return { sessions, isLoading }
}
