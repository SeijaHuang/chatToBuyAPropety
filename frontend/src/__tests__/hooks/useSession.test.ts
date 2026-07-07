import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { useSession } from '@/hooks'
import { useConversationStore } from '@/stores/conversationStore'
import { server } from '@/__tests__/msw/server'
import { mockSessionRestoreResponse } from '@/__tests__/msw/fixtures'
import { ENDPOINTS } from '@/constants/endpoints'

const BASE_URL = 'http://localhost:8000'

beforeEach(() => {
  useConversationStore.setState({
    sessionId: null,
    state: null,
    messages: [],
    routing: null,
    isLoading: false,
  })
})

describe('useSession', () => {
  it('returns isLoading false and isRestored false when disabled', () => {
    const { result } = renderHook(() => useSession('some-session', false))

    expect(result.current.isLoading).toBe(false)
    expect(result.current.isRestored).toBe(false)
  })

  it('does not mutate the store when disabled', () => {
    renderHook(() => useSession('test-session', false))

    expect(useConversationStore.getState().sessionId).toBeNull()
  })

  it('restores session from GET response for real sessionId', async () => {
    const { result } = renderHook(() => useSession('test-session'))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.isRestored).toBe(true)
    expect(useConversationStore.getState().sessionId).toBe('test-session')
    expect(useConversationStore.getState().state?.sessionId).toBe('test-session')
  })

  it('state snapshot does not include conversationHistory after restore', async () => {
    const { result } = renderHook(() => useSession('test-session'))

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    const state = useConversationStore.getState().state
    expect(state).not.toBeNull()
    expect('conversationHistory' in (state ?? {})).toBe(false)
  })

  it('displays resumeMessage as assistant message when provided', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHAT}/:sessionId`, () =>
        HttpResponse.json({
          ok: true,
          data: { resumeMessage: 'Welcome back!', conversationHistory: [], state: mockSessionRestoreResponse.state },
        })
      )
    )

    const { result } = renderHook(() => useSession('test-session'))

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    const msgs = useConversationStore.getState().messages
    expect(msgs).toHaveLength(1)
    expect(msgs[0].content).toBe('Welcome back!')
    expect(msgs[0].role).toBe('assistant')
  })

  it('restores conversation history messages from Redis hit response', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHAT}/:sessionId`, () =>
        HttpResponse.json({
          ok: true,
          data: {
            resumeMessage: null,
            conversationHistory: [
              { role: 'user', content: 'Hi' },
              { role: 'assistant', content: 'Hello!' },
            ],
            state: mockSessionRestoreResponse.state,
          },
        })
      )
    )

    const { result } = renderHook(() => useSession('test-session'))

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    const msgs = useConversationStore.getState().messages
    expect(msgs).toHaveLength(2)
    expect(msgs[0].role).toBe('user')
    expect(msgs[0].content).toBe('Hi')
    expect(msgs[1].role).toBe('assistant')
    expect(msgs[1].content).toBe('Hello!')
  })

  it('falls back to initSession when GET returns 404', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHAT}/:sessionId`, () =>
        HttpResponse.json(
          { error: { code: 'SessionNotFoundError', message: 'Not found', details: {} } },
          { status: 404 }
        )
      )
    )

    const { result } = renderHook(() => useSession('missing-session'))

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.isRestored).toBe(false)
    expect(useConversationStore.getState().sessionId).toBe('missing-session')
    expect(useConversationStore.getState().state).toBeNull()
  })

  it('sets isLoading true while GET is in flight', async () => {
    let resolveRequest!: () => void
    const pendingPromise = new Promise<void>((resolve) => { resolveRequest = resolve })

    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHAT}/:sessionId`, async () => {
        await pendingPromise
        return HttpResponse.json({ ok: true, data: mockSessionRestoreResponse })
      })
    )

    const { result } = renderHook(() => useSession('test-session'))

    await waitFor(() => expect(result.current.isLoading).toBe(true))

    resolveRequest()

    await waitFor(() => expect(result.current.isLoading).toBe(false))
  })
})
