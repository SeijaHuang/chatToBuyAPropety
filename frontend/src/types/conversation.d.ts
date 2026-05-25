// ─── Message Role ─────────────────────────────────────────────────────────────

export const MESSAGE_ROLE = {
  USER:      'user',
  ASSISTANT: 'assistant',
} as const

export type MessageRole = typeof MESSAGE_ROLE[keyof typeof MESSAGE_ROLE]

// ─── Module ID ────────────────────────────────────────────────────────────────

export const MODULE_ID = {
  M1: 'M1_PROPERTY_NEEDS',
  M2: 'M2_LIFESTYLE',
  M3: 'M3_SUBURB_PREFERENCE',
  M4: 'M4_BUDGET',
  COMPLETE: 'COMPLETE',
} as const

export type ModuleID = typeof MODULE_ID[keyof typeof MODULE_ID]

// ─── Session Status ───────────────────────────────────────────────────────────

export const SESSION_STATUS = {
  IN_PROGRESS:           'IN_PROGRESS',
  REQUIREMENTS_COMPLETE: 'REQUIREMENTS_COMPLETE',
} as const

export type SessionStatus = typeof SESSION_STATUS[keyof typeof SESSION_STATUS]

// ─── Submodel Keys ───────────────────────────────────────────────────────────

export const SUBMODEL_KEY = {
  M1: 'm1',
  M2: 'm2',
  M3: 'm3',
  M4: 'm4',
} as const

export type SubmodelKey = typeof SUBMODEL_KEY[keyof typeof SUBMODEL_KEY]

// ─── Sub-model Interfaces ─────────────────────────────────────────────────────

export interface M1PropertyNeeds {
  propertyType:  'house' | 'townhouse' | 'unit' | 'apartment' | 'villa' | 'any' | null
  minBedrooms:   number | null
  maxBedrooms:   number | null
  minBathrooms:  number | null
  minCarspaces:  number | null
  minLandSize:   number | null
  maxLandSize:   number | null
  wantsPool:     boolean | null
  wantsOutdoor:  boolean | null
  wantsStudy:    boolean | null
  intendedUse:   'owner_occupier' | 'investment' | 'both' | null
}

export interface M2Lifestyle {
  householdSize:    number | null
  hasChildren:      boolean | null
  needsSchoolZone:  boolean | null
  hasPets:          boolean | null
  workFromHome:     boolean | null
  targetTenant:     'family' | 'professional' | 'student' | 'any' | null
}

export interface M3SuburbPreference {
  commuteDestination: string | null
  commuteMaxMins:     number | null
  commuteMode:        'train' | 'car' | 'tram' | 'bus' | 'any' | null
  preferredSuburbs:   string[] | null
  excludedSuburbs:    string[] | null
  lifestyleVibe:      'inner_city' | 'suburban' | 'leafy' | 'coastal' | 'any' | null
}

export interface M4Budget {
  budgetMin:       number | null
  budgetMax:       number | null
  depositAmount:   number | null
  preTaxSalary:    number | null
  partnerSalary:   number | null
  isJoint:         boolean | null
  firstHomeBuyer:  boolean | null
  loanTermYears:   number | null
}

export interface CollectedData {
  [SUBMODEL_KEY.M1]: M1PropertyNeeds
  [SUBMODEL_KEY.M2]: M2Lifestyle
  [SUBMODEL_KEY.M3]: M3SuburbPreference
  [SUBMODEL_KEY.M4]: M4Budget
}

import type { BorrowingCapacityResult, BudgetGapResult } from './financial'

export type { BorrowingCapacityResult, BudgetGapResult }

// ─── Core DTO ─────────────────────────────────────────────────────────────────

export interface ConversationStateDTO {
  sessionId:           string
  status:              SessionStatus
  currentModule:       ModuleID
  completionStatus:    { M1: boolean; M2: boolean; M3: boolean; M4: boolean }
  collectedData:       CollectedData
  conversationHistory: Array<{ role: MessageRole; content: string }>
  finalNeeds:         CollectedData | null
  borrowingCapacity:  BorrowingCapacityResult | null
  budgetGap:          BudgetGapResult | null
}

// ─── UI Message (frontend-only, not sent to backend) ─────────────────────────

export interface UIMessage {
  id:                 string
  role:               MessageRole
  content:            string
  isLoading:          boolean
  timestamp:          Date
  borrowingCapacity?: BorrowingCapacityResult
  budgetGap?:         BudgetGapResult
}
