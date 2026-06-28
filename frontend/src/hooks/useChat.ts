'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useConversationStore } from '@/stores/conversationStore'
import { postChat } from '@/services'
import { ERROR_CODE, STORAGE_KEY } from '@/constants'

interface UseChatReturn {
  sendMessage: (content: string) => Promise<void>
  isLoading: boolean
  errorMessage: string | null
  clearError: () => void
}

export function useChat(): UseChatReturn {
  const store = useConversationStore()
  const isLoading: boolean = store.isLoading
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const router = useRouter()

  const clearError = (): void => setErrorMessage(null)

  // Hydrate anonId from localStorage on first mount so subsequent sends include it.
  // Runs once — the store's setAnonId keeps localStorage and state in sync after that.
  useEffect((): void => {
    if (store.anonId === null) {
      const stored: string | null = localStorage.getItem(STORAGE_KEY.ANON_ID)
      if (stored !== null) {
        store.setAnonId(stored)
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const sendMessage = async (content: string): Promise<void> => {
    if (content.trim() === '') return
    if (store.isLoading) return

    const isNewSession: boolean = store.sessionId === null || store.sessionId === 'new'
    const sessionId: string | null = isNewSession ? null : store.sessionId
    // Read anonId from store first, fall back to localStorage in case the
    // useEffect hydration hasn't completed yet (e.g. first send in same tick).
    const anonId: string | null =
      store.anonId ?? localStorage.getItem(STORAGE_KEY.ANON_ID)

    setErrorMessage(null)
    store.setLoading(true)
    store.addUserMessage(content)
    store.setAssistantLoading(true)

    try {
      const response = await postChat(content, sessionId, anonId)

      if (response.ok === true) {
        store.setAnonId(response.data.anonId)
        store.addAssistantMessage(response.data.reply)

        if (isNewSession) {
          store.setSessionFromResponse(response.data.sessionId, response.data.state)
          router.replace(`/chat/${response.data.sessionId}`)
        } else {
          store.setUpdatedState(response.data.state)
        }

        if (response.data.routing !== null) {
          store.setRouting(response.data.routing)
        }
      } else {
        const code: string = response.error.code
        if (code === 'LLM_SERVICE_UNAVAILABLE') {
          setErrorMessage('AI temporarily unavailable. Please try again.')
        } else if (code === ERROR_CODE.NETWORK) {
          setErrorMessage('Connection failed. Check your network.')
        } else {
          setErrorMessage('Something went wrong. Please try again.')
        }
      }
    } finally {
      store.setAssistantLoading(false)
      store.setLoading(false)
    }
  }

  return { sendMessage, isLoading, errorMessage, clearError }
}