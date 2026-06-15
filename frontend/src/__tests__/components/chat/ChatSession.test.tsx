import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChatSession } from '@/components/ChatSession'
import { useConversationStore } from '@/stores/conversationStore'
import { createInitialState } from '@/lib/utils'
import { STORAGE_KEY } from '@/constants/storageKeys'
import { MESSAGE_ROLE } from '@/constants'

vi.mock('uuid', () => ({ v4: () => 'test-id' }))

const initialStoreState = {
  sessionId: null,
  state: null,
  messages: [],
  routing: null,
  isLoading: false,
}

beforeEach(() => {
  useConversationStore.setState(initialStoreState)
  sessionStorage.clear()
})

describe('ChatSession', () => {
  it('calls initSession when no stored session exists', () => {
    render(<ChatSession sessionId="new-session" />)
    expect(useConversationStore.getState().sessionId).toBe('new-session')
  })

  it('restores session from sessionStorage when data exists', () => {
    const dto = createInitialState('existing-session')
    dto.conversationHistory = [{ role: MESSAGE_ROLE.USER, content: 'restored message' }]
    sessionStorage.setItem(
      STORAGE_KEY.CONVERSATION_STATE_PREFIX + 'existing-session',
      JSON.stringify(dto)
    )

    render(<ChatSession sessionId="existing-session" />)

    const messages = useConversationStore.getState().messages
    expect(messages.length).toBeGreaterThan(0)
    expect(messages[0].content).toBe('restored message')
  })

  it('renders ChatInput', () => {
    useConversationStore.setState({
      ...initialStoreState,
      sessionId: 'test-session',
      state: createInitialState('test-session'),
    })

    render(<ChatSession sessionId="test-session" />)

    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('renders messages from store', async () => {
    const dto = createInitialState('msg-session')
    dto.conversationHistory = [{ role: MESSAGE_ROLE.USER, content: 'Hello from store' }]
    sessionStorage.setItem(
      STORAGE_KEY.CONVERSATION_STATE_PREFIX + 'msg-session',
      JSON.stringify(dto)
    )

    render(<ChatSession sessionId="msg-session" />)

    expect(await screen.findByText('Hello from store')).toBeVisible()
  })
})
