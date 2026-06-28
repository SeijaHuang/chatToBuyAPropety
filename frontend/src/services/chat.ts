import { request } from '@/lib/request'
import { ENDPOINTS } from '@/constants/endpoints'
import type { APIResponse, ChatResponse, ConversationStateDTO } from '@/types'

export function postChat(
  message: string,
  sessionId: string | null
): Promise<APIResponse<ChatResponse>> {
  const body: Record<string, unknown> = { message }
  if (sessionId !== null) body.sessionId = sessionId
  return request.post<ChatResponse>(ENDPOINTS.CHAT, body)
}

export function getSession(sessionId: string): Promise<APIResponse<ConversationStateDTO>> {
  return request.get<ConversationStateDTO>(`${ENDPOINTS.CHAT}/${sessionId}`)
}
