import { describe, it, expect } from 'vitest'
import { formatAUD, createInitialState } from '@/lib/utils'
import { SESSION_STATUS, MODULE_ID } from '@/types'

describe('utils', () => {
  describe('formatAUD', () => {
    it('formats a typical property price with dollar sign and commas', () => {
      expect(formatAUD(1200000)).toBe('$1,200,000')
    })

    it('formats zero as $0', () => {
      expect(formatAUD(0)).toBe('$0')
    })

    it('returns no decimal places', () => {
      expect(formatAUD(1200000)).not.toContain('.')
    })

    it('formats a small amount correctly', () => {
      expect(formatAUD(500000)).toBe('$500,000')
    })
  })

  describe('createInitialState', () => {
    it('uses the provided sessionId', () => {
      const state = createInitialState('session-abc')
      expect(state.sessionId).toBe('session-abc')
    })

    it('sets status to IN_PROGRESS', () => {
      const state = createInitialState('s1')
      expect(state.status).toBe(SESSION_STATUS.IN_PROGRESS)
    })

    it('sets currentModule to M1_PROPERTY_NEEDS', () => {
      const state = createInitialState('s1')
      expect(state.currentModule).toBe(MODULE_ID.M1)
    })

    it('sets all completionStatus flags to false', () => {
      const state = createInitialState('s1')
      expect(state.completionStatus).toEqual({ M1: false, M2: false, M3: false, M4: false })
    })

    it('initialises m1 with all null fields', () => {
      const state = createInitialState('s1')
      const m1 = state.collectedData.m1
      expect(m1.propertyType).toBeNull()
      expect(m1.minBedrooms).toBeNull()
      expect(m1.maxBedrooms).toBeNull()
      expect(m1.minBathrooms).toBeNull()
      expect(m1.minCarspaces).toBeNull()
      expect(m1.minLandSize).toBeNull()
      expect(m1.maxLandSize).toBeNull()
      expect(m1.wantsPool).toBeNull()
      expect(m1.wantsOutdoor).toBeNull()
      expect(m1.wantsStudy).toBeNull()
      expect(m1.intendedUse).toBeNull()
    })

    it('initialises m2 with all null fields', () => {
      const state = createInitialState('s1')
      const m2 = state.collectedData.m2
      expect(m2.householdSize).toBeNull()
      expect(m2.hasChildren).toBeNull()
      expect(m2.needsSchoolZone).toBeNull()
      expect(m2.hasPets).toBeNull()
      expect(m2.workFromHome).toBeNull()
      expect(m2.targetTenant).toBeNull()
    })

    it('initialises m3 with all null fields', () => {
      const state = createInitialState('s1')
      const m3 = state.collectedData.m3
      expect(m3.commuteDestination).toBeNull()
      expect(m3.commuteMaxMins).toBeNull()
      expect(m3.commuteMode).toBeNull()
      expect(m3.preferredSuburbs).toBeNull()
      expect(m3.excludedSuburbs).toBeNull()
      expect(m3.lifestyleVibe).toBeNull()
    })

    it('initialises m4 with all null fields including loanTermYears', () => {
      const state = createInitialState('s1')
      const m4 = state.collectedData.m4
      expect(m4.budgetMin).toBeNull()
      expect(m4.budgetMax).toBeNull()
      expect(m4.depositAmount).toBeNull()
      expect(m4.preTaxSalary).toBeNull()
      expect(m4.partnerSalary).toBeNull()
      expect(m4.isJoint).toBeNull()
      expect(m4.firstHomeBuyer).toBeNull()
      expect(m4.loanTermYears).toBeNull()
    })

    it('sets borrowingCapacity to null', () => {
      const state = createInitialState('s1')
      expect(state.borrowingCapacity).toBeNull()
    })

    it('sets budgetGap to null', () => {
      const state = createInitialState('s1')
      expect(state.budgetGap).toBeNull()
    })

    it('sets conversationHistory to empty array', () => {
      const state = createInitialState('s1')
      expect(state.conversationHistory).toEqual([])
    })

    it('returns independent objects on repeated calls with the same id', () => {
      const a = createInitialState('same-id')
      const b = createInitialState('same-id')
      expect(a).not.toBe(b)
    })
  })
})
