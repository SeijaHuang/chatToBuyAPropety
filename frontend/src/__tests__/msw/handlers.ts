import { http, HttpResponse } from 'msw'
import { ENDPOINTS } from '@/constants/endpoints'
import { SUBMODEL_KEY, USER_INTENT } from '@/constants'
import type { ChatResponse, CollectedData, SummaryResponse } from '@/types'

const BASE_URL = 'http://localhost:8000'

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

const mockChatResponse: ChatResponse = {
  reply: 'mock assistant reply',
  extracted: {},
  routing: null,
}

const mockSummaryResponse: SummaryResponse = {
  summaryText: 'mock summary text',
  structured: {
    sessionId: 'test-session',
    generatedAt: '2026-05-26T00:00:00Z',
    schemaVersion: '1.0',
    collected: emptyCollected,
    initialIntent: USER_INTENT.OPEN_ENDED_QUERY,
  },
}

export const handlers = [
  http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () => HttpResponse.json({ ok: true, data: mockChatResponse })),

  http.post(`${BASE_URL}/${ENDPOINTS.CHAT_SUMMARY}`, () => HttpResponse.json({ ok: true, data: mockSummaryResponse })),
]
