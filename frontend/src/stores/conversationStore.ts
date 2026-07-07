'use client'

import { create } from 'zustand'
import { v4 as uuid } from 'uuid'
import type {
  ConversationSnapshotDTO,
  UIMessage,
  RoutingPayload,
  BorrowingCapacityResult,
  BudgetGapResult,
  MessageRole,
  SessionRestoreResponse,
} from '@/types'
import { MESSAGE_ROLE } from '@/constants'

interface ConversationStore {
  sessionId: string | null
  state: ConversationSnapshotDTO | null
  messages: UIMessage[]
  routing: RoutingPayload | null
  isLoading: boolean

  initSession(sessionId: string): void
  setUpdatedState(newState: ConversationSnapshotDTO): void
  setSessionFromResponse(sessionId: string, newState: ConversationSnapshotDTO): void
  restoreSession(response: SessionRestoreResponse): void
  addUserMessage(content: string): void
  addAssistantMessage(content: string): void
  setAssistantLoading(loading: boolean): void
  setLoading(loading: boolean): void
  setRouting(routing: RoutingPayload): void
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

function injectCardMessages(
  prevState: ConversationSnapshotDTO | null,
  newState: ConversationSnapshotDTO
): UIMessage[] {
  const cards: UIMessage[] = []
  if (
    (prevState === null || prevState.borrowingCapacity === null) &&
    newState.borrowingCapacity !== null
  ) {
    cards.push(makeAssistantMessage('', { borrowingCapacity: newState.borrowingCapacity }))
  }
  if (newState.budgetGap?.has_gap === true) {
    cards.push(makeAssistantMessage('', { budgetGap: newState.budgetGap }))
  }
  return cards
}

export const useConversationStore = create<ConversationStore>((set, get) => ({
  sessionId: null,
  state: null,
  messages: [],
  routing: null,
  isLoading: false,

  initSession(sessionId: string): void {
    set({ sessionId, state: null, messages: [], routing: null, isLoading: false })
  },

  setUpdatedState(newState: ConversationSnapshotDTO): void {
    const prevState: ConversationSnapshotDTO | null = get().state
    set({ state: newState })
    const cards: UIMessage[] = injectCardMessages(prevState, newState)
    if (cards.length > 0) {
      set((s) => ({ messages: [...s.messages, ...cards] }))
    }
  },

  setSessionFromResponse(sessionId: string, newState: ConversationSnapshotDTO): void {
    const prevState: ConversationSnapshotDTO | null = get().state
    set({ sessionId, state: newState })
    const cards: UIMessage[] = injectCardMessages(prevState, newState)
    if (cards.length > 0) {
      set((s) => ({ messages: [...s.messages, ...cards] }))
    }
  },

  restoreSession(response: SessionRestoreResponse): void {
    const { resumeMessage, state, conversationHistory } = response
    const messages: UIMessage[] = []

    if (conversationHistory.length > 0) {
      for (const msg of conversationHistory) {
        messages.push({
          id: uuid(),
          role: msg.role as MessageRole,
          content: msg.content,
          isLoading: false,
          timestamp: new Date(),
        })
      }
    } else if (resumeMessage !== null) {
      messages.push(makeAssistantMessage(resumeMessage))
    }

    if (state.borrowingCapacity !== null) {
      messages.push(makeAssistantMessage('', { borrowingCapacity: state.borrowingCapacity }))
    }
    if (state.budgetGap?.has_gap === true) {
      messages.push(makeAssistantMessage('', { budgetGap: state.budgetGap }))
    }
    set({
      sessionId: state.sessionId,
      state,
      messages,
      routing: null,
      isLoading: false,
    })
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

  clearSession(): void {
    set({ sessionId: null, state: null, messages: [], routing: null, isLoading: false })
  },
}))
