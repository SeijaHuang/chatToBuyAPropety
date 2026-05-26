import { request } from '@/lib/request'
import { ENDPOINTS } from '@/constants/endpoints'
import type { APIResponse, ChatResponse, ConversationStateDTO } from '@/types'

export function postChat(
  message: string,
  state: ConversationStateDTO
): Promise<APIResponse<ChatResponse>> {
  return request.post<ChatResponse>(ENDPOINTS.CHAT, { message, state })
}
