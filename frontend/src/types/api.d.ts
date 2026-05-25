import type { ConversationStateDTO } from './conversation'
import type { RoutingPayload } from './routing'
import type { UserNeeds } from './user_needs'

export interface ChatResponse {
  reply:        string
  extracted:    Record<string, unknown>
  updatedState: ConversationStateDTO
  routing:      RoutingPayload | null
}

export interface SummaryResponse {
  summaryText: string
  structured:  UserNeeds
}
