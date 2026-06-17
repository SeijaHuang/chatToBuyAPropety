import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/__tests__/msw/server'
import { ENDPOINTS } from '@/constants/endpoints'
import { ERROR_CODE } from '@/constants/errorCodes'
import { postChat } from '@/services/chat'

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
