import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useSession } from '@/hooks'
import { useConversationStore } from '@/stores/conversationStore'
import { createInitialState } from '@/lib/utils'
import { STORAGE_KEY } from '@/constants/storageKeys'

beforeEach(() => {
  useConversationStore.setState({
    sessionId: null,
    state: null,
    messages: [],
    routing: null,
    isLoading: false,
  })
  sessionStorage.clear()
})

describe('useSession', () => {
  it('restores from storage on mount', () => {
    const dto = createInitialState('abc')
    sessionStorage.setItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + 'abc', JSON.stringify(dto))

    renderHook(() => useSession('abc'))

    expect(useConversationStore.getState().state?.sessionId).toBe('abc')
  })

  it('inits session when storage not found', () => {
    renderHook(() => useSession('new-sess'))

    expect(useConversationStore.getState().sessionId).toBe('new-sess')
  })

  it('returns isRestored true when found', () => {
    const dto = createInitialState('abc')
    sessionStorage.setItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + 'abc', JSON.stringify(dto))

    const { result } = renderHook(() => useSession('abc'))

    expect(result.current.isRestored).toBe(true)
  })

  it('returns isRestored false when not found', () => {
    const { result } = renderHook(() => useSession('missing'))

    expect(result.current.isRestored).toBe(false)
  })
})
