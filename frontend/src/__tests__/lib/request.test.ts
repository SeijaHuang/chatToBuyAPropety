import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { InternalAxiosRequestConfig } from 'axios'

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
