import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { InternalAxiosRequestConfig } from 'axios'
import { http, HttpResponse } from 'msw'
import { server } from '@/__tests__/msw/server'
import { request, axiosClient } from '@/lib/request'
import { ERROR_CODE } from '@/constants/errorCodes'
import { ENDPOINTS } from '@/constants/endpoints'

const BASE_URL = 'http://localhost:8000'

describe('request.post', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns ok:true and the data payload on a 200 response', async () => {
    const result = await request.post<{ reply: string }>(ENDPOINTS.CHAT, { message: 'hi', sessionId: 's1' })
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.data.reply).toBe('mock assistant reply')
    }
  })

  it('returns ok:false with network_error code when no response is received', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () => HttpResponse.error()),
    )
    const result = await request.post(ENDPOINTS.CHAT, { message: 'hi', sessionId: 's1' })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe(ERROR_CODE.NETWORK)
    }
  })

  it('returns ok:false with backend error code when server returns a valid error envelope', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () =>
        HttpResponse.json(
          { error: { code: 'LLM_SERVICE_UNAVAILABLE', message: 'Service down', details: {} } },
          { status: 503 },
        ),
      ),
    )
    const result = await request.post(ENDPOINTS.CHAT, { message: 'hi', sessionId: 's1' })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe('LLM_SERVICE_UNAVAILABLE')
      expect(result.error.message).toBe('Service down')
    }
  })

  it('returns ok:false with unknown code when server returns a non-envelope error body', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () =>
        HttpResponse.json('Internal Server Error', { status: 500 }),
      ),
    )
    const result = await request.post(ENDPOINTS.CHAT, { message: 'hi', sessionId: 's1' })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe(ERROR_CODE.UNKNOWN)
    }
  })

  it('returns ok:false with unknown code for a non-axios thrown error', async () => {
    vi.spyOn(axiosClient, 'post').mockRejectedValueOnce(new Error('Non-axios programming error'))
    const result = await request.post(ENDPOINTS.CHAT, {})
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe(ERROR_CODE.UNKNOWN)
    }
  })

  it('returns ok:false with unknown code when envelope is missing required fields', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () =>
        HttpResponse.json({ error: { code: 42 } }, { status: 400 }),
      ),
    )
    const result = await request.post(ENDPOINTS.CHAT, { message: 'hi', sessionId: 's1' })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe(ERROR_CODE.UNKNOWN)
    }
  })
})

describe('request.get', () => {
  it('returns ok:true and the data payload on a 200 response', async () => {
    const result = await request.get<{ status: string }>('health')
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.data.status).toBe('healthy')
    }
  })

  it('returns ok:false with network_error code on network failure', async () => {
    server.use(
      http.get(`${BASE_URL}/health`, () => HttpResponse.error()),
    )
    const result = await request.get('health')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe(ERROR_CODE.NETWORK)
    }
  })
})

describe('axiosClient', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('test_axios_instance_has_correct_base_url', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_BASE_URL', 'http://localhost:8000')
    const { axiosClient } = await import('@/lib/request')
    expect(axiosClient.defaults.baseURL).toBe('http://localhost:8000')
  })

  it('test_axios_instance_timeout_is_30000', async () => {
    const { axiosClient } = await import('@/lib/request')
    expect(axiosClient.defaults.timeout).toBe(30_000)
  })

  it('test_request_interceptor_passes_through_config', async () => {
    const { axiosClient } = await import('@/lib/request')
    const fakeConfig: InternalAxiosRequestConfig = {
      headers: {} as InternalAxiosRequestConfig['headers'],
      url: '/test',
      method: 'get',
    }
    const handlers = (
      axiosClient.interceptors.request as unknown as {
        handlers: Array<{ fulfilled: (c: InternalAxiosRequestConfig) => InternalAxiosRequestConfig }>
      }
    ).handlers
    const result: InternalAxiosRequestConfig = handlers[0].fulfilled(fakeConfig)
    expect(result).toBe(fakeConfig)
  })
})
