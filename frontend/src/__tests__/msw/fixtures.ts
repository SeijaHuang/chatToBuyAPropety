import type { BorrowingCapacityResult, BudgetGapResult } from '@/types/financial'
import type { ChatResponse, ChatSessionDTO, SummaryResponse } from '@/types/api'
import type { CollectedData, ConversationStateDTO, ConversationSnapshotDTO } from '@/types/conversation'
import type { RoutingPayload } from '@/types/routing'
import { SUBMODEL_KEY, MODULE_ID, SESSION_STATUS } from '@/constants/conversation'
import { USER_INTENT, EXECUTION_MODE, TRIGGER_SOURCE } from '@/constants/routing'

const emptyCollected: CollectedData = {
  [SUBMODEL_KEY.M1]: {
    propertyType: null,
    minBedrooms: null,
    maxBedrooms: null,
    minBathrooms: null,
    minCarspaces: null,
    minLandSize: null,
    maxLandSize: null,
    wantsPool: null,
    wantsOutdoor: null,
    wantsStudy: null,
    intendedUse: null,
  },
  [SUBMODEL_KEY.M2]: {
    householdSize: null,
    hasChildren: null,
    needsSchoolZone: null,
    hasPets: null,
    workFromHome: null,
    targetTenant: null,
  },
  [SUBMODEL_KEY.M3]: {
    commuteDestination: null,
    commuteMaxMins: null,
    commuteMode: null,
    preferredSuburbs: null,
    excludedSuburbs: null,
    lifestyleVibe: null,
  },
  [SUBMODEL_KEY.M4]: {
    budgetMin: null,
    budgetMax: null,
    depositAmount: null,
    preTaxSalary: null,
    partnerSalary: null,
    isJoint: null,
    firstHomeBuyer: null,
    loanTermYears: null,
  },
}

export const mockBorrowingCapacity: BorrowingCapacityResult = {
  estimated_capacity: 560000,
  monthly_repayment: 2450,
  based_on_salary: 95000,
  is_joint: false,
  annual_rate: 6.25,
  loan_term_years: 30,
  rate_source: 'RBA F5 lending rate indicator (2026-05)',
  disclaimer:
    'This is an estimate only based on RBA F5 indicator rate of 6.25% p.a. It is not financial advice. Actual borrowing capacity depends on your lender, living expenses, and credit history. Consult a licensed mortgage broker.',
}

export const mockBudgetGap: BudgetGapResult = {
  has_gap: true,
  budget_max: 600000,
  market_median: 850000,
  gap_amount: 250000,
  gap_percentage: 29.4,
  reference_suburb: 'Brunswick',
  suggested_actions: [
    'Consider suburbs with lower median prices',
    'Explore government grants for first home buyers',
    'Review your deposit strategy',
  ],
}

export const mockSnapshot: ConversationSnapshotDTO = {
  sessionId: 'test-session',
  status: SESSION_STATUS.IN_PROGRESS,
  currentModule: MODULE_ID.M1,
  completionStatus: { M1: false, M2: false, M3: false, M4: false },
  collectedData: emptyCollected,
  finalNeeds: null,
  borrowingCapacity: null,
  budgetGap: null,
}

export const mockChatResponse: ChatResponse = {
  reply: 'mock assistant reply',
  extracted: {},
  sessionId: 'test-session',
  state: mockSnapshot,
  routing: null,
}

const mockRoutingPayload: RoutingPayload = {
  intent: USER_INTENT.LIST_PROPERTIES,
  sessionId: 'test-session-routing',
  userNeeds: {
    sessionId: 'test-session-routing',
    generatedAt: '2026-05-26T00:00:00Z',
    schemaVersion: '1.0',
    collected: emptyCollected,
    initialIntent: USER_INTENT.OPEN_ENDED_QUERY,
  },
  executionMode: EXECUTION_MODE.CODE_DRIVEN,
  agentsHint: ['property_search'],
  triggeredAt: '2026-05-26T00:00:00Z',
  triggerSource: TRIGGER_SOURCE.AUTO_COMPLETE,
}

export const mockChatResponseWithRouting: ChatResponse = {
  reply: 'I have gathered everything I need.',
  extracted: {},
  sessionId: 'test-session',
  state: mockSnapshot,
  routing: mockRoutingPayload,
}

export const mockSummaryResponse: SummaryResponse = {
  summaryText: 'mock summary text',
  structured: {
    sessionId: 'test-session',
    generatedAt: '2026-05-26T00:00:00Z',
    schemaVersion: '1.0',
    collected: emptyCollected,
    initialIntent: USER_INTENT.OPEN_ENDED_QUERY,
  },
}

export const mockConversationState: ConversationStateDTO = {
  sessionId: 'test-session',
  status: SESSION_STATUS.IN_PROGRESS,
  currentModule: MODULE_ID.M1,
  completionStatus: { M1: false, M2: false, M3: false, M4: false },
  collectedData: emptyCollected,
  conversationHistory: [],
  finalNeeds: null,
  borrowingCapacity: null,
  budgetGap: null,
}

export const mockChatSessions: ChatSessionDTO[] = [
  {
    sessionId: 'session-001',
    status: 'IN_PROGRESS',
    initialIntent: USER_INTENT.LIST_PROPERTIES,
    createdAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    updatedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    completedAt: null,
  },
  {
    sessionId: 'session-002',
    status: 'IN_PROGRESS',
    initialIntent: null,
    createdAt: new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString(),
    updatedAt: new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString(),
    completedAt: null,
  },
]
