import axios, { isAxiosError, type AxiosInstance, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { ERROR_CODE, ERROR_MESSAGE } from '@/constants/errorCodes'
import type { APIResponse, ErrorDetail } from '@/types'

const axiosClient: AxiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

axiosClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    // @todo P1: inject auth token — config.headers.Authorization = `Bearer ${token}`
    return config
  }
)

function normalizeError(err: unknown): ErrorDetail {
  // Non-axios error (e.g. a thrown string, programming error)
  if (!isAxiosError(err)) {
    return { code: ERROR_CODE.UNKNOWN, message: ERROR_MESSAGE.UNEXPECTED, details: {} }
  }

  // No response — request never reached the server (network down, DNS, CORS preflight)
  if (!err.response) {
    return { code: ERROR_CODE.NETWORK, message: ERROR_MESSAGE.NETWORK, details: {} }
  }

  // Server responded but body is not our error envelope shape
  const data: unknown = err.response.data
  if (
    typeof data !== 'object' ||
    data === null ||
    !('error' in data) ||
    typeof (data as Record<string, unknown>).error !== 'object' ||
    (data as Record<string, unknown>).error === null
  ) {
    return { code: ERROR_CODE.UNKNOWN, message: ERROR_MESSAGE.UNEXPECTED, details: {} }
  }

  // Envelope present but missing required fields (code / message / details)
  const envelope = (data as Record<string, unknown>).error as Record<string, unknown>
  if (
    typeof envelope.code !== 'string' ||
    typeof envelope.message !== 'string' ||
    typeof envelope.details !== 'object' ||
    envelope.details === null
  ) {
    return { code: ERROR_CODE.UNKNOWN, message: ERROR_MESSAGE.UNEXPECTED, details: {} }
  }

  // Well-formed backend error envelope — { error: { code, message, details } }
  return {
    code: envelope.code,
    message: envelope.message,
    details: envelope.details as Record<string, unknown>,
  }
}

export { axiosClient }

export const request = {
  async post<TData>(url: string, data?: unknown): Promise<APIResponse<TData>> {
    try {
      const response: AxiosResponse<TData> = await axiosClient.post<TData>(url, data)
      return { ok: true, data: response.data }
    } catch (err) {
      return { ok: false, error: normalizeError(err) }
    }
  },

  async get<TData>(url: string, params?: unknown): Promise<APIResponse<TData>> {
    try {
      const response: AxiosResponse<TData> = await axiosClient.get<TData>(url, { params })
      return { ok: true, data: response.data }
    } catch (err) {
      return { ok: false, error: normalizeError(err) }
    }
  },
}
