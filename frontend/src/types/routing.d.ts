import type { UserNeeds } from './user_needs'

// ─── User Intent ──────────────────────────────────────────────────────────────
// 与后端 EUserIntent (intent_router.py) 严格对齐，共 4 个值

export const USER_INTENT = {
  RECOMMEND_SUBURBS: 'recommend_suburbs',
  LIST_PROPERTIES:   'list_properties',
  PROPERTY_DETAIL:   'property_detail',
  OPEN_ENDED_QUERY:  'open_ended_query',
} as const

export type EUserIntent = typeof USER_INTENT[keyof typeof USER_INTENT]

// ─── Execution Mode ───────────────────────────────────────────────────────────

export const EXECUTION_MODE = {
  CODE_DRIVEN:  'code_driven',
  AGENTIC_LOOP: 'agentic_loop',
} as const

export type EExecutionMode = typeof EXECUTION_MODE[keyof typeof EXECUTION_MODE]

// ─── Trigger Source ───────────────────────────────────────────────────────────

export const TRIGGER_SOURCE = {
  AUTO_COMPLETE: 'auto_complete',
  KEYWORD:       'keyword',
  MANUAL:        'manual',
} as const

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
