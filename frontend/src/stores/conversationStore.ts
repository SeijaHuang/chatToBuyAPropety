'use client'

import { create } from 'zustand'
import { v4 as uuid } from 'uuid'
import type {
  ConversationStateDTO,
  UIMessage,
  RoutingPayload,
  BorrowingCapacityResult,
  BudgetGapResult,
  MessageRole,
} from '@/types'
import { MESSAGE_ROLE } from '@/constants'
import { createInitialState } from '@/lib/utils'
import { STORAGE_KEY } from '@/constants/storageKeys'

interface ConversationStore {
  sessionId: string | null
  state: ConversationStateDTO | null
  messages: UIMessage[]
  routing: RoutingPayload | null
  isLoading: boolean

  initSession(sessionId: string): void
  setUpdatedState(newState: ConversationStateDTO): void
  addUserMessage(content: string): void
  addAssistantMessage(content: string): void
  setAssistantLoading(loading: boolean): void
  setLoading(loading: boolean): void
  setRouting(routing: RoutingPayload): void
  restoreFromStorage(sessionId: string): boolean
  clearSession(): void
}

function makeAssistantMessage(
  content: string,
  extra?: { borrowingCapacity?: BorrowingCapacityResult; budgetGap?: BudgetGapResult }
): UIMessage {
  return {
    id: uuid(),
    role: MESSAGE_ROLE.ASSISTANT as MessageRole,
    content,
    isLoading: false,
    timestamp: new Date(),
    ...extra,
  }
}

export const useConversationStore = create<ConversationStore>((set, get) => ({
  sessionId: null,
  state: null,
  messages: [],
  routing: null,
  isLoading: false,

  initSession(sessionId: string): void {
    const freshState: ConversationStateDTO = createInitialState(sessionId)
    sessionStorage.setItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + sessionId, JSON.stringify(freshState))
    set({ sessionId, state: freshState, messages: [], routing: null, isLoading: false })
  },

  setUpdatedState(newState: ConversationStateDTO): void {
    const prevState: ConversationStateDTO | null = get().state
    set({ state: newState })
    sessionStorage.setItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + newState.sessionId, JSON.stringify(newState))

    const cardMessages: UIMessage[] = []

    if (prevState?.borrowingCapacity === null && newState.borrowingCapacity !== null) {
      cardMessages.push(makeAssistantMessage('', { borrowingCapacity: newState.borrowingCapacity }))
    }

    if (newState.budgetGap?.has_gap === true) {
      cardMessages.push(makeAssistantMessage('', { budgetGap: newState.budgetGap }))
    }

    if (cardMessages.length > 0) {
      set((s) => ({ messages: [...s.messages, ...cardMessages] }))
    }
  },

  addUserMessage(content: string): void {
    const message: UIMessage = {
      id: uuid(),
      role: MESSAGE_ROLE.USER as MessageRole,
      content,
      isLoading: false,
      timestamp: new Date(),
    }
    set((s) => ({ messages: [...s.messages, message] }))
  },

  addAssistantMessage(content: string): void {
    set((s) => {
      const msgs: UIMessage[] = [...s.messages]
      const loadingIdx: number = msgs.map((m) => m.isLoading).lastIndexOf(true)
      if (loadingIdx !== -1) {
        msgs[loadingIdx] = { ...msgs[loadingIdx], content, isLoading: false }
      } else {
        msgs.push(makeAssistantMessage(content))
      }
      return { messages: msgs }
    })
  },

  setAssistantLoading(loading: boolean): void {
    if (loading) {
      const placeholder: UIMessage = {
        id: uuid(),
        role: MESSAGE_ROLE.ASSISTANT as MessageRole,
        content: '',
        isLoading: true,
        timestamp: new Date(),
      }
      set((s) => ({ messages: [...s.messages, placeholder] }))
    } else {
      set((s) => {
        const msgs: UIMessage[] = [...s.messages]
        for (let i: number = msgs.length - 1; i >= 0; i--) {
          if (msgs[i].role === MESSAGE_ROLE.ASSISTANT && msgs[i].isLoading) {
            msgs[i] = { ...msgs[i], isLoading: false }
            break
          }
        }
        return { messages: msgs }
      })
    }
  },

  setLoading(loading: boolean): void {
    set({ isLoading: loading })
  },

  setRouting(routing: RoutingPayload): void {
    set({ routing })
  },

  restoreFromStorage(sessionId: string): boolean {
    const raw: string | null = sessionStorage.getItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + sessionId)
    if (raw === null) {
      return false
    }

    const restoredState: ConversationStateDTO = JSON.parse(raw) as ConversationStateDTO

    const messages: UIMessage[] = restoredState.conversationHistory.map(
      (entry): UIMessage => ({
        id: uuid(),
        role: entry.role,
        content: entry.content,
        isLoading: false,
        timestamp: new Date(),
      })
    )

    if (restoredState.borrowingCapacity !== null) {
      messages.push(
        makeAssistantMessage('', { borrowingCapacity: restoredState.borrowingCapacity })
      )
    }

    if (restoredState.budgetGap?.has_gap === true) {
      messages.push(makeAssistantMessage('', { budgetGap: restoredState.budgetGap }))
    }

    set({ sessionId, state: restoredState, messages, routing: null, isLoading: false })
    return true
  },

  clearSession(): void {
    const currentSessionId: string | null = get().sessionId
    if (currentSessionId !== null) {
      sessionStorage.removeItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + currentSessionId)
    }
    set({ sessionId: null, state: null, messages: [], routing: null, isLoading: false })
  },
}))
