import { USER_INTENT, EXECUTION_MODE, TRIGGER_SOURCE } from '../constants/routing'
import type { UserNeeds } from './user_needs'

export type EUserIntent    = typeof USER_INTENT[keyof typeof USER_INTENT]
export type EExecutionMode = typeof EXECUTION_MODE[keyof typeof EXECUTION_MODE]
export type ETriggerSource = typeof TRIGGER_SOURCE[keyof typeof TRIGGER_SOURCE]

// ─── Routing Payload ──────────────────────────────────────────────────────────

export interface RoutingPayload {
  intent:        EUserIntent
  sessionId:     string
  userNeeds:     UserNeeds
  executionMode: EExecutionMode
  agentsHint:    string[]
  triggeredAt:   string
  triggerSource: ETriggerSource
}

export type { UserNeeds }
