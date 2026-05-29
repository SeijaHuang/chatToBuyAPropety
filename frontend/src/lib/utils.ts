import type { ConversationStateDTO, M1PropertyNeeds, M2Lifestyle, M3SuburbPreference, M4Budget, CollectedData } from '@/types'
import { SESSION_STATUS, MODULE_ID, SUBMODEL_KEY } from '@/types'

/** Formats an AUD integer for display. formatAUD(1200000) → '$1,200,000' */
export function formatAUD(amount: number): string {
  const formatter: Intl.NumberFormat = new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    maximumFractionDigits: 0,
  })
  return formatter.format(amount)
}

/** Returns a fresh ConversationStateDTO with all fields null and status IN_PROGRESS. */
export function createInitialState(sessionId: string): ConversationStateDTO {
  const m1: M1PropertyNeeds = {
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
  }

  const m2: M2Lifestyle = {
    householdSize: null,
    hasChildren: null,
    needsSchoolZone: null,
    hasPets: null,
    workFromHome: null,
    targetTenant: null,
  }

  const m3: M3SuburbPreference = {
    commuteDestination: null,
    commuteMaxMins: null,
    commuteMode: null,
    preferredSuburbs: null,
    excludedSuburbs: null,
    lifestyleVibe: null,
  }

  const m4: M4Budget = {
    budgetMin: null,
    budgetMax: null,
    depositAmount: null,
    preTaxSalary: null,
    partnerSalary: null,
    isJoint: null,
    firstHomeBuyer: null,
    loanTermYears: null,
  }

  const collectedData: CollectedData = {
    [SUBMODEL_KEY.M1]: m1,
    [SUBMODEL_KEY.M2]: m2,
    [SUBMODEL_KEY.M3]: m3,
    [SUBMODEL_KEY.M4]: m4,
  }

  return {
    sessionId,
    status: SESSION_STATUS.IN_PROGRESS,
    currentModule: MODULE_ID.M1,
    completionStatus: { M1: false, M2: false, M3: false, M4: false },
    collectedData,
    conversationHistory: [],
    finalNeeds: null,
    borrowingCapacity: null,
    budgetGap: null,
  }
}
