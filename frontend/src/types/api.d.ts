import type { ConversationSnapshotDTO } from './conversation'
import type { RoutingPayload } from './routing'
import type { UserNeeds } from './user_needs'

// --- Error envelope ---

export interface ErrorDetail {
  code: string
  message: string
  details: Record<string, unknown>
}

export interface ErrorResponse {
  ok: false
  error: ErrorDetail
}

// --- Success envelope ---

export interface SuccessResponse<TData> {
  ok: true
  data: TData
}

// --- Discriminated union for all API responses ---

export type APIResponse<TData> = SuccessResponse<TData> | ErrorResponse

// --- Domain response payloads ---

export interface ChatResponse {
  reply: string
  extracted: Record<string, unknown>
  sessionId: string
  state: ConversationSnapshotDTO
  routing: RoutingPayload | null
}

export interface SummaryResponse {
  summaryText: string
  structured: UserNeeds
}
