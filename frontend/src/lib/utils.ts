import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { ConversationStateDTO, M1PropertyNeeds, M2Lifestyle, M3SuburbPreference, M4Budget, CollectedData } from '@/types'
import { SESSION_STATUS, MODULE_ID, SUBMODEL_KEY } from '@/constants'

/** Merges Tailwind classes with conflict resolution. Last class wins on conflict. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/** Formats an AUD integer for display. formatAUD(1200000) → '$1,200,000' */
export function formatAUD(amount: number): string {
  const formatter: Intl.NumberFormat = new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    maximumFractionDigits: 0,
  })
  return formatter.format(amount)
}

/** Formats an ISO 8601 timestamp as a human-readable relative time string.
 *  formatRelativeTime('...') → 'just now' / '5 minutes ago' / 'yesterday' / '3 days ago' */
export function formatRelativeTime(iso: string): string {
  const diffMs: number = Date.now() - new Date(iso).getTime()
  const diffSec: number = Math.floor(diffMs / 1000)

  if (diffSec < 60) return 'just now'

  const rtf: Intl.RelativeTimeFormat = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
  const diffMin: number = Math.floor(diffSec / 60)
  if (diffMin < 60) return rtf.format(-diffMin, 'minute')

  const diffHour: number = Math.floor(diffMin / 60)
  if (diffHour < 24) return rtf.format(-diffHour, 'hour')

  const diffDay: number = Math.floor(diffHour / 24)
  if (diffDay < 7) return rtf.format(-diffDay, 'day')

  const diffWeek: number = Math.floor(diffDay / 7)
  return rtf.format(-diffWeek, 'week')
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
