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

  it('store state retains sessionId after successful send', async () => {
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    const storeState = useConversationStore.getState().state
    expect(storeState?.sessionId).toBe('test-session')
  })

  it('sets errorMessage and does not add error text to messages on non-ok response', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () =>
        HttpResponse.json(
          { error: { code: 'INTERNAL', message: 'fail', details: {} } },
          { status: 500 }
        )
      )
    )

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    expect(result.current.errorMessage).toBe('Something went wrong. Please try again.')
    const messages = useConversationStore.getState().messages
    expect(
      messages.every((m) => m.content !== 'Sorry, something went wrong. Please try again.')
    ).toBe(true)
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

  it('does nothing when content is empty string', async () => {
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('')
    })

    expect(useConversationStore.getState().messages).toHaveLength(0)
  })

  it('does nothing when content is only whitespace', async () => {
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('   ')
    })

    expect(useConversationStore.getState().messages).toHaveLength(0)
  })

  it('shows assistant loading bubble before response arrives', async () => {
    const { result } = renderHook(() => useChat())
    const loadingStates: boolean[] = []

    act(() => {
      void result.current.sendMessage('hello')
      loadingStates.push(useConversationStore.getState().messages.some((m) => m.isLoading))
    })

    await act(async () => {})

    expect(loadingStates.some(Boolean)).toBe(true)
  })

  it('sets errorMessage on 503 response', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () =>
        HttpResponse.json(
          { error: { code: 'LLM_SERVICE_UNAVAILABLE', message: 'fail', details: {} } },
          { status: 503 }
        )
      )
    )

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    expect(result.current.errorMessage).toMatch(/unavailable/i)
  })

  it('sets errorMessage on network error', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () => HttpResponse.error())
    )

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    expect(result.current.errorMessage).toBeTruthy()
  })

  it('sets routing when response contains routing', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () =>
        HttpResponse.json({
          reply: 'done',
          extracted: {},
          routing: { intent: 'list_properties', session_id: 'test-session' },
        })
      )
    )

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    expect(useConversationStore.getState().routing?.intent).toBe('list_properties')
  })

  it('clears loading state in finally even on error', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () =>
        HttpResponse.json(
          { error: { code: 'INTERNAL', message: 'fail', details: {} } },
          { status: 500 }
        )
      )
    )

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('hello')
    })

    expect(useConversationStore.getState().isLoading).toBe(false)
  })
})
