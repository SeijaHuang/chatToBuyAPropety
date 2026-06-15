import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { useChat } from '@/hooks'
import { useConversationStore } from '@/stores/conversationStore'
import { createInitialState } from '@/lib/utils'
import { ENDPOINTS } from '@/constants/endpoints'
import { server } from '@/__tests__/msw/server'

vi.mock('uuid', () => ({ v4: () => 'test-id' }))

const BASE_URL = 'http://localhost:8000'

const initialStoreState = {
  sessionId: 'test-session',
  state: createInitialState('test-session'),
  messages: [],
  routing: null,
  isLoading: false,
}

beforeEach(() => {
  useConversationStore.setState(initialStoreState)
})

describe('useChat', () => {
  it('appends user message immediately on sendMessage', async () => {
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    const messages = useConversationStore.getState().messages
    const userMsg = messages.find((m) => m.role === 'user')
    expect(userMsg).toBeDefined()
    expect(userMsg?.content).toBe('hello')
  })

  it('appends assistant reply after successful API response', async () => {
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    const messages = useConversationStore.getState().messages
    const assistantMsg = messages.find((m) => m.role === 'assistant' && m.content !== '')
    expect(assistantMsg).toBeDefined()
    expect(assistantMsg?.content).toBe('mock assistant reply')
  })

  it('calls setUpdatedState with the response updatedState', async () => {
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    const storeState = useConversationStore.getState().state
    expect(storeState?.sessionId).toBe('test-session')
  })

  it('appends error assistant message when API returns a non-ok response', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () =>
        HttpResponse.json({ error: { code: 'INTERNAL', message: 'fail' } }, { status: 500 })
      )
    )

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    const messages = useConversationStore.getState().messages
    const errorMsg = messages.find((m) => m.role === 'assistant')
    expect(errorMsg?.content).toBe('Sorry, something went wrong. Please try again.')
  })

  it('sets isLoading true during request, false after', async () => {
    const loadingDuring: boolean[] = []

    const { result } = renderHook(() => useChat())

    const promise = act(async () => {
      const p = result.current.sendMessage('hello')
      loadingDuring.push(useConversationStore.getState().isLoading)
      await p
    })

    await promise

    expect(useConversationStore.getState().isLoading).toBe(false)
  })

  it('is a no-op when state is null', async () => {
    useConversationStore.setState({ ...initialStoreState, state: null })

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    expect(useConversationStore.getState().messages).toHaveLength(0)
  })

  it('is a no-op when isLoading is already true', async () => {
    useConversationStore.setState({ ...initialStoreState, isLoading: true })

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    expect(useConversationStore.getState().messages).toHaveLength(0)
  })
})
