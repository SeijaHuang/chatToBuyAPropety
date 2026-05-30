import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useConversationStore } from '@/stores/conversationStore'
import { SESSION_STATUS, MODULE_ID } from '@/constants'
import type { ConversationStateDTO, RoutingPayload, BorrowingCapacityResult, BudgetGapResult } from '@/types'
import { createInitialState } from '@/lib/utils'
import { STORAGE_KEY } from '@/constants/storageKeys'

vi.mock('uuid', () => ({ v4: () => 'test-id' }))

const initialState = {
  sessionId:  null,
  state:      null,
  messages:   [],
  routing:    null,
  isLoading:  false,
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
  sessionStorage.clear()
})

describe('conversationStore', () => {
  describe('initSession', () => {
    it('sets the sessionId', () => {
      useConversationStore.getState().initSession('s1')
      expect(useConversationStore.getState().sessionId).toBe('s1')
    })

    it('sets status to IN_PROGRESS via createInitialState', () => {
      useConversationStore.getState().initSession('s1')
      expect(useConversationStore.getState().state?.status).toBe(SESSION_STATUS.IN_PROGRESS)
    })

    it('writes state to sessionStorage', () => {
      useConversationStore.getState().initSession('s1')
      const raw: string | null = sessionStorage.getItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + 's1')
      expect(raw).not.toBeNull()
      const parsed = JSON.parse(raw!)
      expect(parsed.sessionId).toBe('s1')
    })

    it('clears any existing messages', () => {
      useConversationStore.setState({ messages: [{ id: 'x', role: 'user', content: 'hi', isLoading: false, timestamp: new Date() }] })
      useConversationStore.getState().initSession('s1')
      expect(useConversationStore.getState().messages).toHaveLength(0)
    })
  })

  describe('setUpdatedState', () => {
    it('completely replaces state (no merge)', () => {
      useConversationStore.getState().initSession('s1')
      const newState: ConversationStateDTO = makeDTO('s1')
      newState.currentModule = MODULE_ID.M2
      useConversationStore.getState().setUpdatedState(newState)
      expect(useConversationStore.getState().state?.currentModule).toBe(MODULE_ID.M2)
    })

    it('does not retain fields from the previous state', () => {
      useConversationStore.getState().initSession('s1')
      const prev: ConversationStateDTO = { ...makeDTO('s1'), currentModule: MODULE_ID.M3 }
      useConversationStore.setState({ state: prev })
      const next: ConversationStateDTO = makeDTO('s1')
      useConversationStore.getState().setUpdatedState(next)
      expect(useConversationStore.getState().state?.currentModule).toBe(MODULE_ID.M1)
    })

    it('writes updated state to sessionStorage', () => {
      useConversationStore.getState().initSession('s1')
      const newState: ConversationStateDTO = makeDTO('s1')
      useConversationStore.getState().setUpdatedState(newState)
      const raw: string | null = sessionStorage.getItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + 's1')
      expect(raw).not.toBeNull()
    })

    it('appends borrowingCapacity card message when first non-null', () => {
      useConversationStore.getState().initSession('s1')
      const newState: ConversationStateDTO = { ...makeDTO('s1'), borrowingCapacity: mockBorrowingCapacity }
      useConversationStore.getState().setUpdatedState(newState)
      const msgs = useConversationStore.getState().messages
      expect(msgs).toHaveLength(1)
      expect(msgs[0].borrowingCapacity).toEqual(mockBorrowingCapacity)
    })

    it('does not append borrowingCapacity card when already present', () => {
      useConversationStore.getState().initSession('s1')
      const withCapacity: ConversationStateDTO = { ...makeDTO('s1'), borrowingCapacity: mockBorrowingCapacity }
      useConversationStore.setState({ state: withCapacity })
      const newState: ConversationStateDTO = { ...makeDTO('s1'), borrowingCapacity: mockBorrowingCapacity }
      useConversationStore.getState().setUpdatedState(newState)
      expect(useConversationStore.getState().messages).toHaveLength(0)
    })

    it('appends budgetGap card message when has_gap is true', () => {
      useConversationStore.getState().initSession('s1')
      const newState: ConversationStateDTO = { ...makeDTO('s1'), budgetGap: mockBudgetGap }
      useConversationStore.getState().setUpdatedState(newState)
      const msgs = useConversationStore.getState().messages
      expect(msgs).toHaveLength(1)
      expect(msgs[0].budgetGap).toEqual(mockBudgetGap)
    })

    it('does not append budgetGap card when has_gap is false', () => {
      useConversationStore.getState().initSession('s1')
      const gapFalse: BudgetGapResult = { ...mockBudgetGap, has_gap: false }
      const newState: ConversationStateDTO = { ...makeDTO('s1'), budgetGap: gapFalse }
      useConversationStore.getState().setUpdatedState(newState)
      expect(useConversationStore.getState().messages).toHaveLength(0)
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

  describe('restoreFromStorage', () => {
    it('returns true and restores state when key exists', () => {
      const dto: ConversationStateDTO = makeDTO('s1')
      sessionStorage.setItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + 's1', JSON.stringify(dto))
      const result: boolean = useConversationStore.getState().restoreFromStorage('s1')
      expect(result).toBe(true)
      expect(useConversationStore.getState().state?.sessionId).toBe('s1')
    })

    it('rebuilds messages from conversationHistory', () => {
      const dto: ConversationStateDTO = makeDTO('s1')
      dto.conversationHistory = [{ role: 'user', content: 'hello' }]
      sessionStorage.setItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + 's1', JSON.stringify(dto))
      useConversationStore.getState().restoreFromStorage('s1')
      const msgs = useConversationStore.getState().messages
      expect(msgs).toHaveLength(1)
      expect(msgs[0].content).toBe('hello')
      expect(msgs[0].role).toBe('user')
    })

    it('appends borrowingCapacity card if present in restored state', () => {
      const dto: ConversationStateDTO = { ...makeDTO('s1'), borrowingCapacity: mockBorrowingCapacity }
      sessionStorage.setItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + 's1', JSON.stringify(dto))
      useConversationStore.getState().restoreFromStorage('s1')
      const msgs = useConversationStore.getState().messages
      const cardMsg = msgs.find((m) => m.borrowingCapacity !== undefined)
      expect(cardMsg).toBeDefined()
      expect(cardMsg?.borrowingCapacity).toEqual(mockBorrowingCapacity)
    })

    it('appends budgetGap card if has_gap is true in restored state', () => {
      const dto: ConversationStateDTO = { ...makeDTO('s1'), budgetGap: mockBudgetGap }
      sessionStorage.setItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + 's1', JSON.stringify(dto))
      useConversationStore.getState().restoreFromStorage('s1')
      const msgs = useConversationStore.getState().messages
      const cardMsg = msgs.find((m) => m.budgetGap !== undefined)
      expect(cardMsg).toBeDefined()
      expect(cardMsg?.budgetGap).toEqual(mockBudgetGap)
    })

    it('returns false and leaves state unchanged when key is absent', () => {
      const result: boolean = useConversationStore.getState().restoreFromStorage('missing')
      expect(result).toBe(false)
      expect(useConversationStore.getState().state).toBeNull()
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

    it('removes the sessionStorage key', () => {
      useConversationStore.getState().initSession('s1')
      expect(sessionStorage.getItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + 's1')).not.toBeNull()
      useConversationStore.getState().clearSession()
      expect(sessionStorage.getItem(STORAGE_KEY.CONVERSATION_STATE_PREFIX + 's1')).toBeNull()
    })
  })
})
