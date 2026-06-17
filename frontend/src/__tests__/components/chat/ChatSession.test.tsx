import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChatSession } from '@/components/ChatSession'
import { useChat } from '@/hooks/useChat'
import { useConversationStore } from '@/stores/conversationStore'
import { createInitialState } from '@/lib/utils'
import { MESSAGE_ROLE } from '@/constants'
import type { RoutingPayload, UIMessage } from '@/types'

vi.mock('uuid', () => ({ v4: () => 'test-id' }))
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('@/hooks/useSession', () => ({ useSession: vi.fn() }))
vi.mock('@/hooks/useChat', () => ({
  useChat: vi.fn(() => ({
    sendMessage: vi.fn(),
    isLoading: false,
    errorMessage: null,
    clearError: vi.fn(),
  })),
}))

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
  vi.mocked(useChat).mockImplementation(() => ({
    sendMessage: vi.fn(),
    isLoading: false,
    errorMessage: null,
    clearError: vi.fn(),
  }))
})

describe('ChatSession', () => {
  it('renders ChatInput', () => {
    useConversationStore.setState({
      ...initialStoreState,
      sessionId: 'test-session',
      state: createInitialState('test-session'),
    })

    render(<ChatSession sessionId="test-session" />)

    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('renders messages from store', () => {
    const userMsg: UIMessage = {
      id: 'msg-1',
      role: MESSAGE_ROLE.USER,
      content: 'Hello from store',
      isLoading: false,
      timestamp: new Date(),
    }
    useConversationStore.setState({
      ...initialStoreState,
      sessionId: 'msg-session',
      state: createInitialState('msg-session'),
      messages: [userMsg],
    })

    render(<ChatSession sessionId="msg-session" />)

    expect(screen.getByText('Hello from store')).toBeVisible()
  })

  it('shows routing CTA when routing is non-null', () => {
    useConversationStore.setState({
      ...initialStoreState,
      sessionId: 'test-session',
      state: createInitialState('test-session'),
      routing: { intent: 'list_properties', session_id: 'test-session' } as unknown as RoutingPayload,
    })

    render(<ChatSession sessionId="test-session" />)

    expect(screen.getByText(/ready to find properties/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /view matching properties/i })).toBeInTheDocument()
  })

  it('does not show routing CTA when routing is null', () => {
    useConversationStore.setState({
      ...initialStoreState,
      sessionId: 'test-session',
      state: createInitialState('test-session'),
      routing: null,
    })

    render(<ChatSession sessionId="test-session" />)

    expect(screen.queryByText(/ready to find properties/i)).not.toBeInTheDocument()
  })

  it('shows disclaimer text', () => {
    useConversationStore.setState({
      ...initialStoreState,
      sessionId: 'test-session',
      state: createInitialState('test-session'),
    })

    render(<ChatSession sessionId="test-session" />)

    expect(screen.getByText(/homi ai can make mistakes/i)).toBeVisible()
  })

  it('shows error message when errorMessage is non-null', () => {
    vi.mocked(useChat).mockImplementationOnce(() => ({
      sendMessage: vi.fn(),
      isLoading: false,
      errorMessage: 'AI temporarily unavailable. Please try again.',
      clearError: vi.fn(),
    }))
    useConversationStore.setState({
      ...initialStoreState,
      sessionId: 'test-session',
      state: createInitialState('test-session'),
    })

    render(<ChatSession sessionId="test-session" />)

    expect(screen.getByRole('alert')).toHaveTextContent(/unavailable/i)
  })
})
