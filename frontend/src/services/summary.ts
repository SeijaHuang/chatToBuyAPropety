import { request } from '@/lib/request'
import { ENDPOINTS } from '@/constants/endpoints'
import { USER_INTENT } from '@/constants'
import type { APIResponse, CollectedData, EUserIntent, SummaryResponse } from '@/types'

// @todo P1: getSession(sessionId: string)
// @todo P1: deleteSession(sessionId: string)

export function postChatSummary(
  collectedData: CollectedData,
  sessionId: string,
  initialIntent: EUserIntent = USER_INTENT.OPEN_ENDED_QUERY
): Promise<APIResponse<SummaryResponse>> {
  return request.post<SummaryResponse>(ENDPOINTS.CHAT_SUMMARY, {
    collectedData,
    sessionId,
    initialIntent,
  })
}
