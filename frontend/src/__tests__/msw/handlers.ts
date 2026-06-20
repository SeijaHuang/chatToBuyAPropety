import { http, HttpResponse } from 'msw'
import { ENDPOINTS } from '@/constants/endpoints'
import { mockChatResponse, mockSummaryResponse, mockConversationState } from './fixtures'

const BASE_URL = 'http://localhost:8000'

export const handlers = [
  http.get(`${BASE_URL}/health`, () =>
    HttpResponse.json({ ok: true, data: { status: 'healthy' } }),
  ),

  http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () => HttpResponse.json({ ok: true, data: mockChatResponse })),

  http.post(`${BASE_URL}/${ENDPOINTS.CHAT_SUMMARY}`, () => HttpResponse.json({ ok: true, data: mockSummaryResponse })),

  http.get(`${BASE_URL}/${ENDPOINTS.CHAT}/:sessionId`, () =>
    HttpResponse.json({ ok: true, data: mockConversationState }),
  ),
]
