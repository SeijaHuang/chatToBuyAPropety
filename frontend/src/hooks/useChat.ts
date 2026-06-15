'use client'

import { useConversationStore } from '@/stores/conversationStore'
import { postChat } from '@/services'
import type { ConversationStateDTO } from '@/types'

interface UseChatReturn {
  sendMessage: (content: string) => Promise<void>
  isLoading: boolean
}

export function useChat(): UseChatReturn {
  const store = useConversationStore()
  const isLoading: boolean = store.isLoading

  const sendMessage = async (content: string): Promise<void> => {
    const state: ConversationStateDTO | null = store.state
    if (state === null || store.isLoading) return

    store.addUserMessage(content)
    store.setAssistantLoading(true)
    store.setLoading(true)

    const response = await postChat(content, state)
    if (response.ok === true) {
      store.addAssistantMessage(response.data.reply)
      store.setUpdatedState(response.data.updatedState)
      if (response.data.routing !== null) {
        store.setRouting(response.data.routing)
      }
    } else {
      store.addAssistantMessage('Sorry, something went wrong. Please try again.')
      console.error(response.error)
    }
    store.setAssistantLoading(false)
    store.setLoading(false)
  }

  return { sendMessage, isLoading }
}
