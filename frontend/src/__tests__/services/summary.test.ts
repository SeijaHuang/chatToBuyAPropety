import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/__tests__/msw/server'
import { ENDPOINTS } from '@/constants/endpoints'
import { postChatSummary } from '@/services/summary'
import { SUBMODEL_KEY, USER_INTENT } from '@/types'
import type { CollectedData } from '@/types'

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

describe('postChatSummary', () => {
  it('test_post_chat_summary_returns_ok_true_on_success', async () => {
    const result = await postChatSummary(emptyCollected, 'test-session')
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.data.summaryText).toBe('mock summary text')
    }
  })

  it('test_post_chat_summary_default_intent_is_open_ended_query', async () => {
    let capturedBody: unknown = null
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT_SUMMARY}`, async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json({ summaryText: 'ok', structured: {} })
      })
    )
    await postChatSummary(emptyCollected, 'test-session')
    expect((capturedBody as Record<string, unknown>).initialIntent).toBe(
      USER_INTENT.OPEN_ENDED_QUERY
    )
  })

  it('test_post_chat_summary_returns_ok_false_on_error', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT_SUMMARY}`, () =>
        HttpResponse.json(
          { error: { code: 'SUMMARY_VALIDATION_ERROR', message: 'No data', details: {} } },
          { status: 400 }
        )
      )
    )
    const result = await postChatSummary(emptyCollected, 'test-session')
    expect(result.ok).toBe(false)
  })

  it('test_error_detail_has_code_message_details_shape', async () => {
    server.use(
      http.post(`${BASE_URL}/${ENDPOINTS.CHAT_SUMMARY}`, () =>
        HttpResponse.json(
          { error: { code: 'SOME_ERROR', message: 'Something went wrong', details: { field: 'x' } } },
          { status: 422 }
        )
      )
    )
    const result = await postChatSummary(emptyCollected, 'test-session')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error).toMatchObject({
        code: 'SOME_ERROR',
        message: 'Something went wrong',
        details: { field: 'x' },
      })
    }
  })
})
