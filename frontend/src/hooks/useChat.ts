'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useConversationStore } from '@/stores/conversationStore'
import { postChat } from '@/services'
import { ERROR_CODE } from '@/constants/errorCodes'

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

  const sendMessage = async (content: string): Promise<void> => {
    if (content.trim() === '') return
    if (store.isLoading) return

    const isNewSession: boolean = store.sessionId === null || store.sessionId === 'new'
    const sessionId: string | null = isNewSession ? null : store.sessionId

    setErrorMessage(null)
    store.setLoading(true)
    store.addUserMessage(content)
    store.setAssistantLoading(true)

    try {
      const response = await postChat(content, sessionId)

      if (response.ok === true) {
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
