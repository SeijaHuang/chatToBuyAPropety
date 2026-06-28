import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useConversationStore } from '@/stores/conversationStore'
import { SESSION_STATUS, MODULE_ID } from '@/constants'
import type { ConversationSnapshotDTO, ConversationStateDTO, RoutingPayload, BorrowingCapacityResult, BudgetGapResult } from '@/types'
import { createInitialState } from '@/lib/utils'

vi.mock('uuid', () => ({ v4: () => 'test-id' }))

const initialState = {
  sessionId:  null,
  state:      null,
  messages:   [],
  routing:    null,
  isLoading:  false,
}

function makeSnapshot(sessionId: string): ConversationSnapshotDTO {
  const { conversationHistory: _, ...snapshot } = createInitialState(sessionId)
  return snapshot
}

function makeDTO(sessionId: string): ConversationStateDTO {
  return createInitialState(sessionId)
}

const mockBorrowingCapacity: BorrowingCapacityResult = {
  estimated_capacity: 800000,
  monthly_repayment:  3200,
  based_on_salary:    120000,
  is_joint:           false,
  annual_rate:        0.06,
  loan_term_years:    25,
  rate_source:        'RBA',
  disclaimer:         'Estimate only.',
}

const mockBudgetGap: BudgetGapResult = {
  has_gap:           true,
  budget_max:        700000,
  market_median:     900000,
  gap_amount:        200000,
  gap_percentage:    22,
  reference_suburb:  'Docklands',
  suggested_actions: ['Expand search radius'],
}

beforeEach(() => {
  useConversationStore.setState(initialState)
})

describe('conversationStore', () => {
  describe('initSession', () => {
    it('sets the sessionId', () => {
      useConversationStore.getState().initSession('s1')
      expect(useConversationStore.getState().sessionId).toBe('s1')
    })

    it('leaves state as null (backend is state authority in P1)', () => {
      useConversationStore.getState().initSession('s1')
      expect(useConversationStore.getState().state).toBeNull()
    })

    it('clears any existing messages', () => {
      useConversationStore.setState({ messages: [{ id: 'x', role: 'user', content: 'hi', isLoading: false, timestamp: new Date() }] })
      useConversationStore.getState().initSession('s1')
      expect(useConversationStore.getState().messages).toHaveLength(0)
    })
  })

  describe('setUpdatedState', () => {
    it('completely replaces state (no merge)', () => {
      const newState: ConversationSnapshotDTO = { ...makeSnapshot('s1'), currentModule: MODULE_ID.M2 }
      useConversationStore.getState().setUpdatedState(newState)
      expect(useConversationStore.getState().state?.currentModule).toBe(MODULE_ID.M2)
    })

    it('does not retain fields from the previous state', () => {
      const prev: ConversationSnapshotDTO = { ...makeSnapshot('s1'), currentModule: MODULE_ID.M3 }
      useConversationStore.setState({ state: prev })
      const next: ConversationSnapshotDTO = makeSnapshot('s1')
      useConversationStore.getState().setUpdatedState(next)
      expect(useConversationStore.getState().state?.currentModule).toBe(MODULE_ID.M1)
    })

    it('appends borrowingCapacity card message when first non-null', () => {
      useConversationStore.setState({ state: makeSnapshot('s1') })
      const newState: ConversationSnapshotDTO = { ...makeSnapshot('s1'), borrowingCapacity: mockBorrowingCapacity }
      useConversationStore.getState().setUpdatedState(newState)
      const msgs = useConversationStore.getState().messages
      expect(msgs).toHaveLength(1)
      expect(msgs[0].borrowingCapacity).toEqual(mockBorrowingCapacity)
    })

    it('does not append borrowingCapacity card when already present', () => {
      const withCapacity: ConversationSnapshotDTO = { ...makeSnapshot('s1'), borrowingCapacity: mockBorrowingCapacity }
      useConversationStore.setState({ state: withCapacity })
      const newState: ConversationSnapshotDTO = { ...makeSnapshot('s1'), borrowingCapacity: mockBorrowingCapacity }
      useConversationStore.getState().setUpdatedState(newState)
      expect(useConversationStore.getState().messages).toHaveLength(0)
    })

    it('appends budgetGap card message when has_gap is true', () => {
      const newState: ConversationSnapshotDTO = { ...makeSnapshot('s1'), budgetGap: mockBudgetGap }
      useConversationStore.getState().setUpdatedState(newState)
      const msgs = useConversationStore.getState().messages
      expect(msgs).toHaveLength(1)
      expect(msgs[0].budgetGap).toEqual(mockBudgetGap)
    })

    it('does not append budgetGap card when has_gap is false', () => {
      const gapFalse: BudgetGapResult = { ...mockBudgetGap, has_gap: false }
      const newState: ConversationSnapshotDTO = { ...makeSnapshot('s1'), budgetGap: gapFalse }
      useConversationStore.getState().setUpdatedState(newState)
      expect(useConversationStore.getState().messages).toHaveLength(0)
    })
  })

  describe('setSessionFromResponse', () => {
    it('sets sessionId and state together', () => {
      const snapshot: ConversationSnapshotDTO = makeSnapshot('s1')
      useConversationStore.getState().setSessionFromResponse('s1', snapshot)
      expect(useConversationStore.getState().sessionId).toBe('s1')
      expect(useConversationStore.getState().state?.sessionId).toBe('s1')
    })

    it('injects borrowingCapacity card when first non-null', () => {
      const snapshot: ConversationSnapshotDTO = { ...makeSnapshot('s1'), borrowingCapacity: mockBorrowingCapacity }
      useConversationStore.getState().setSessionFromResponse('s1', snapshot)
      const msgs = useConversationStore.getState().messages
      expect(msgs).toHaveLength(1)
      expect(msgs[0].borrowingCapacity).toEqual(mockBorrowingCapacity)
    })

    it('state status is IN_PROGRESS after response', () => {
      const snapshot: ConversationSnapshotDTO = makeSnapshot('s1')
      useConversationStore.getState().setSessionFromResponse('s1', snapshot)
      expect(useConversationStore.getState().state?.status).toBe(SESSION_STATUS.IN_PROGRESS)
    })
  })

  describe('restoreSession', () => {
    it('sets sessionId from the full state', () => {
      const dto: ConversationStateDTO = makeDTO('s1')
      useConversationStore.getState().restoreSession(dto)
      expect(useConversationStore.getState().sessionId).toBe('s1')
    })

    it('state does not include conversationHistory', () => {
      const dto: ConversationStateDTO = makeDTO('s1')
      useConversationStore.getState().restoreSession(dto)
      const state = useConversationStore.getState().state
      expect(state).not.toBeNull()
      expect('conversationHistory' in (state ?? {})).toBe(false)
    })

    it('rebuilds messages from conversationHistory', () => {
      const dto: ConversationStateDTO = { ...makeDTO('s1'), conversationHistory: [{ role: 'user', content: 'hello' }] }
      useConversationStore.getState().restoreSession(dto)
      const msgs = useConversationStore.getState().messages
      expect(msgs).toHaveLength(1)
      expect(msgs[0].content).toBe('hello')
      expect(msgs[0].role).toBe('user')
    })

    it('appends borrowingCapacity card if present in restored state', () => {
      const dto: ConversationStateDTO = { ...makeDTO('s1'), borrowingCapacity: mockBorrowingCapacity }
      useConversationStore.getState().restoreSession(dto)
      const msgs = useConversationStore.getState().messages
      const cardMsg = msgs.find((m) => m.borrowingCapacity !== undefined)
      expect(cardMsg).toBeDefined()
      expect(cardMsg?.borrowingCapacity).toEqual(mockBorrowingCapacity)
    })

    it('appends budgetGap card if has_gap is true in restored state', () => {
      const dto: ConversationStateDTO = { ...makeDTO('s1'), budgetGap: mockBudgetGap }
      useConversationStore.getState().restoreSession(dto)
      const msgs = useConversationStore.getState().messages
      const cardMsg = msgs.find((m) => m.budgetGap !== undefined)
      expect(cardMsg).toBeDefined()
      expect(cardMsg?.budgetGap).toEqual(mockBudgetGap)
    })
  })

  describe('addUserMessage', () => {
    it('appends a user message to messages', () => {
      useConversationStore.getState().addUserMessage('hello')
      const msgs = useConversationStore.getState().messages
      expect(msgs).toHaveLength(1)
      expect(msgs[0].role).toBe('user')
      expect(msgs[0].content).toBe('hello')
    })

    it('sets isLoading to false on the new message', () => {
      useConversationStore.getState().addUserMessage('hello')
      expect(useConversationStore.getState().messages[0].isLoading).toBe(false)
    })
  })

  describe('addAssistantMessage', () => {
    it('replaces the last loading assistant message with content', () => {
      useConversationStore.getState().setAssistantLoading(true)
      useConversationStore.getState().addAssistantMessage('reply')
      const msgs = useConversationStore.getState().messages
      expect(msgs).toHaveLength(1)
      expect(msgs[0].content).toBe('reply')
      expect(msgs[0].isLoading).toBe(false)
    })

    it('appends a new message if no loading message exists', () => {
      useConversationStore.getState().addAssistantMessage('reply')
      const msgs = useConversationStore.getState().messages
      expect(msgs).toHaveLength(1)
      expect(msgs[0].content).toBe('reply')
    })
  })

  describe('setAssistantLoading', () => {
    it('appends a loading assistant message when true', () => {
      useConversationStore.getState().setAssistantLoading(true)
      const msgs = useConversationStore.getState().messages
      expect(msgs).toHaveLength(1)
      expect(msgs[0].role).toBe('assistant')
      expect(msgs[0].isLoading).toBe(true)
    })

    it('clears isLoading on last assistant message when false', () => {
      useConversationStore.getState().setAssistantLoading(true)
      useConversationStore.getState().setAssistantLoading(false)
      const msgs = useConversationStore.getState().messages
      expect(msgs[0].isLoading).toBe(false)
    })
  })

  describe('setLoading', () => {
    it('toggles isLoading correctly', () => {
      useConversationStore.getState().setLoading(true)
      expect(useConversationStore.getState().isLoading).toBe(true)
      useConversationStore.getState().setLoading(false)
      expect(useConversationStore.getState().isLoading).toBe(false)
    })
  })

  describe('setRouting', () => {
    it('starts as null', () => {
      expect(useConversationStore.getState().routing).toBeNull()
    })

    it('stores the routing payload', () => {
      const payload: RoutingPayload = {
        intent:        'open_ended_query',
        sessionId:     's1',
        userNeeds:     {} as never,
        executionMode: 'code_driven',
        agentsHint:    [],
        triggeredAt:   '2026-01-01T00:00:00Z',
        triggerSource: 'auto_complete',
      }
      useConversationStore.getState().setRouting(payload)
      expect(useConversationStore.getState().routing).toEqual(payload)
    })
  })

  describe('clearSession', () => {
    it('resets all state fields to initial values', () => {
      useConversationStore.getState().initSession('s1')
      useConversationStore.getState().addUserMessage('hi')
      useConversationStore.getState().clearSession()
      const s = useConversationStore.getState()
      expect(s.sessionId).toBeNull()
      expect(s.state).toBeNull()
      expect(s.messages).toHaveLength(0)
      expect(s.routing).toBeNull()
      expect(s.isLoading).toBe(false)
    })
  })
})
