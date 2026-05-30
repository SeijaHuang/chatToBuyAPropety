import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/__tests__/msw/server'
import { ENDPOINTS } from '@/constants/endpoints'
import { ERROR_CODE } from '@/constants/errorCodes'
import { postChat } from '@/services/chat'
import { MODULE_ID, SESSION_STATUS, SUBMODEL_KEY } from '@/constants'
import type { CollectedData, ConversationStateDTO } from '@/types'

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

const mockState: ConversationStateDTO = {
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

describe('postChat', () => {
  it('test_post_chat_returns_ok_true_on_success', async () => {
    const result = await postChat('hello', mockState)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.data.reply).toBe('mock assistant reply')
    }
  })

  it('test_post_chat_returns_ok_false_on_503', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () =>
        HttpResponse.json(
          { error: { code: 'LLM_SERVICE_UNAVAILABLE', message: 'Service down', details: {} } },
          { status: 503 }
        )
      )
    )
    const result = await postChat('hello', mockState)
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe('LLM_SERVICE_UNAVAILABLE')
    }
  })

  it('test_post_chat_returns_network_error_code_when_no_response', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT}`, () => HttpResponse.error())
    )
    const result = await postChat('hello', mockState)
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error.code).toBe(ERROR_CODE.NETWORK)
    }
  })
})
