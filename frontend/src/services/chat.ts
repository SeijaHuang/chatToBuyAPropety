import { request } from '@/lib/request'
import { ENDPOINTS } from '@/constants/endpoints'
import type { APIResponse, ChatResponse, ChatSessionDTO, SessionRestoreResponse } from '@/types'

export function postChat(
  message: string,
  sessionId: string | null,
): Promise<APIResponse<ChatResponse>> {
  return request.post<ChatResponse>(ENDPOINTS.CHAT, { message, sessionId })
}

export function getSession(sessionId: string): Promise<APIResponse<SessionRestoreResponse>> {
  return request.get<SessionRestoreResponse>(`${ENDPOINTS.CHAT}/${sessionId}`)
}

export function getChats(): Promise<APIResponse<ChatSessionDTO[]>> {
  return request.get<ChatSessionDTO[]>(ENDPOINTS.CHATS)
}
