import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { useChatHistory } from '@/hooks'
import { ENDPOINTS } from '@/constants/endpoints'
import { server } from '@/__tests__/msw/server'
import type { ChatSessionDTO } from '@/types'

const BASE_URL = 'http://localhost:8000'

function makeSessions(count: number): ChatSessionDTO[] {
  return Array.from({ length: count }, (_, i) => ({
    sessionId: `session-${i + 1}`,
    status: 'IN_PROGRESS',
    initialIntent: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    completedAt: null,
  }))
}

describe('useChatHistory', () => {
  beforeEach(() => {
    // default handler in handlers.ts returns mockChatSessions (2 items)
  })

  it('fetches chats on mount', async () => {
    const { result } = renderHook(() => useChatHistory())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.sessions.length).toBeGreaterThan(0)
  })

  it('truncates to 10 sessions when more than 10 returned', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHATS}`, () =>
        HttpResponse.json({ ok: true, data: makeSessions(12) }),
      ),
    )

    const { result } = renderHook(() => useChatHistory())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.sessions).toHaveLength(10)
  })

  it('returns empty array on API error 400', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHATS}`, () =>
        HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'Missing cookie', details: {} } },
          { status: 400 },
        ),
      ),
    )

    const { result } = renderHook(() => useChatHistory())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.sessions).toEqual([])
  })

  it('returns empty array on network error', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHATS}`, () => HttpResponse.error()),
    )

    const { result } = renderHook(() => useChatHistory())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.sessions).toEqual([])
  })

  it('sets isLoading false after successful fetch', async () => {
    const { result } = renderHook(() => useChatHistory())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.isLoading).toBe(false)
  })

  it('sets isLoading false after failed fetch', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHATS}`, () =>
        HttpResponse.json(
          { error: { code: 'INTERNAL', message: 'fail', details: {} } },
          { status: 500 },
        ),
      ),
    )

    const { result } = renderHook(() => useChatHistory())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.isLoading).toBe(false)
  })
})
