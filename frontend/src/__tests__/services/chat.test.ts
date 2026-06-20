import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/__tests__/msw/server'
import { ENDPOINTS } from '@/constants/endpoints'
import { ERROR_CODE } from '@/constants/errorCodes'
import { postChat, getSession } from '@/services/chat'

const BASE_URL = 'http://localhost:8000'
const TEST_SESSION_ID = 'test-session'

describe('postChat', () => {
  it('test_post_chat_returns_ok_true_on_success', async () => {
    const result = await postChat('hello', TEST_SESSION_ID)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.data.reply).toBe('mock assistant reply')
    }
  })

  it('test_post_chat_returns_ok_false_on_503', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () =>
        HttpResponse.json(
          { error: { code: 'LLM_SERVICE_UNAVAILABLE', message: 'Service down', details: {} } },
          { status: 503 }
        )
      )
    )
    const result = await postChat('hello', TEST_SESSION_ID)
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe('LLM_SERVICE_UNAVAILABLE')
    }
  })

  it('test_post_chat_returns_network_error_code_when_no_response', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () => HttpResponse.error())
    )
    const result = await postChat('hello', TEST_SESSION_ID)
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe(ERROR_CODE.NETWORK)
    }
  })
})

describe('getSession', () => {
  it('sends a GET request to the correct URL including the sessionId', async () => {
    const result = await getSession(TEST_SESSION_ID)
    expect(result.ok).toBe(true)
  })

  it('returns the ConversationStateDTO on success', async () => {
    const result = await getSession(TEST_SESSION_ID)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.data.sessionId).toBe('test-session')
    }
  })

  it('returns ok:false on error', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHAT}/:sessionId`, () =>
        HttpResponse.json(
          { error: { code: 'NOT_FOUND', message: 'Session not found', details: {} } },
          { status: 404 },
        ),
      ),
    )
    const result = await getSession('nonexistent')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe('NOT_FOUND')
    }
  })

  it('returns ok:false with network error code on network failure', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHAT}/:sessionId`, () => HttpResponse.error()),
    )
    const result = await getSession(TEST_SESSION_ID)
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe(ERROR_CODE.NETWORK)
    }
  })
})
