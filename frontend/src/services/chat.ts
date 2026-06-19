import { request } from '@/lib/request'
import { ENDPOINTS } from '@/constants/endpoints'
import type { APIResponse, ChatResponse, ConversationStateDTO } from '@/types'

export function postChat(
  message: string,
  sessionId: string
): Promise<APIResponse<ChatResponse>> {
  return request.post<ChatResponse>(ENDPOINTS.CHAT, { message, sessionId })
}

export function getSession(sessionId: string): Promise<APIResponse<ConversationStateDTO>> {
  return request.get<ConversationStateDTO>(`${ENDPOINTS.CHAT}/${sessionId}`)
}
