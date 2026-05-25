import axios, {
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
  isAxiosError,
} from 'axios'
import type { ErrorResponse } from '@/types'

const NETWORK_ERROR: ErrorResponse = {
  ok: false,
  error: { code: 'network_error', message: 'Connection failed', details: {} },
}

export class APIError extends Error {
  readonly status: number
  readonly response: ErrorResponse

  constructor(status: number, response: ErrorResponse) {
    super(response.error.message)
    this.name = 'APIError'
    this.status = status
    this.response = response
  }
}

function isErrorResponse(v: unknown): v is ErrorResponse {
  if (typeof v !== 'object' || v === null) return false
  const obj: Record<string, unknown> = v as Record<string, unknown>
  if (obj.ok !== false) return false
  if (typeof obj.error !== 'object' || obj.error === null) return false
  const inner: Record<string, unknown> = obj.error as Record<string, unknown>
  return typeof inner.code === 'string' && typeof inner.message === 'string'
}

const axiosClient: AxiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

axiosClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => config,
)

axiosClient.interceptors.response.use(
  (response: AxiosResponse): AxiosResponse => response,
  (error: unknown): never => {
    if (!isAxiosError(error) || !error.response) {
      throw new APIError(0, NETWORK_ERROR)
    }

    const { status, data } = error.response
    const body: ErrorResponse = isErrorResponse(data)
      ? data
      : { ok: false, error: { code: 'unknown_error', message: 'An unexpected error occurred', details: {} } }

    throw new APIError(status, body)
  },
)

export default axiosClient
