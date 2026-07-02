import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { SideNavBar } from '@/components/layout/SideNavBar'
import { useConversationStore } from '@/stores/conversationStore'
import { createInitialState } from '@/lib/utils'
import { ENDPOINTS } from '@/constants/endpoints'
import { server } from '@/__tests__/msw/server'
import type { ChatSessionDTO } from '@/types'

const mockPush = vi.hoisted(() => vi.fn())

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

const BASE_URL = 'http://localhost:8000'

const { conversationHistory: _ch, ...mockSnap } = createInitialState('test-session')

const defaultProps = {
  collapsed: false,
  onToggleCollapse: vi.fn(),
  activePath: '/',
}

function renderSidebar(props: Partial<typeof defaultProps> = {}) {
  return render(<SideNavBar {...defaultProps} {...props} />)
}

beforeEach(() => {
  useConversationStore.setState({
    sessionId: 'test-session',
    state: mockSnap,
    messages: [],
    routing: null,
    isLoading: false,
  })
  mockPush.mockClear()
})

describe('SideNavBar', () => {
  it('renders intent label for known intent (list_properties → "Property Search")', async () => {
    renderSidebar()
    expect(await screen.findByText('Property Search')).toBeInTheDocument()
  })

  it('renders "New Conversation" for null initialIntent', async () => {
    renderSidebar()
    const labels = await screen.findAllByText('New Conversation')
    expect(labels.length).toBeGreaterThan(0)
  })

  it('renders relative time for each session entry', async () => {
    renderSidebar()
    // The default fixtures have timestamps 2h and 25h ago
    await waitFor(() => {
      expect(screen.getAllByText(/hours ago|yesterday/i).length).toBeGreaterThan(0)
    })
  })

  it('active session has aria-current="page"', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHATS}`, () =>
        HttpResponse.json({
          ok: true,
          data: [
            {
              sessionId: 'active-session',
              status: 'IN_PROGRESS',
              initialIntent: 'list_properties',
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
              completedAt: null,
            } satisfies ChatSessionDTO,
          ],
        }),
      ),
    )

    renderSidebar({ activePath: '/chat/active-session' })

    await waitFor(() => {
      const activeBtn = screen.getByRole('button', { name: /Open conversation/i })
      expect(activeBtn).toHaveAttribute('aria-current', 'page')
    })
  })

  it('active session has highlight background class', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHATS}`, () =>
        HttpResponse.json({
          ok: true,
          data: [
            {
              sessionId: 'active-session',
              status: 'IN_PROGRESS',
              initialIntent: null,
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
              completedAt: null,
            } satisfies ChatSessionDTO,
          ],
        }),
      ),
    )

    renderSidebar({ activePath: '/chat/active-session' })

    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /Open conversation/i })
      expect(btn.className).toContain('bg-surface-container')
    })
  })

  it('shows 3 skeleton items while loading', () => {
    // Override the handler to never resolve (simulate slow network)
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHATS}`, async () => {
        await new Promise(() => {}) // never resolves
        return HttpResponse.json({ ok: true, data: [] })
      }),
    )

    renderSidebar()

    const busyContainer = document.querySelector('[aria-busy="true"]')
    expect(busyContainer).not.toBeNull()
    expect(busyContainer?.children).toHaveLength(3)
  })

  it('shows "No conversations yet" when sessions array is empty', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHATS}`, () =>
        HttpResponse.json({ ok: true, data: [] }),
      ),
    )

    renderSidebar()

    expect(await screen.findByText('No conversations yet')).toBeInTheDocument()
  })

  it('navigates to /chat/[sessionId] when entry is clicked', async () => {
    const user = userEvent.setup()
    renderSidebar()

    const buttons = await screen.findAllByRole('button', { name: /Open conversation/i })
    await user.click(buttons[0])

    expect(mockPush).toHaveBeenCalledWith('/chat/session-001')
  })

  it('does not render history list when collapsed is true', () => {
    renderSidebar({ collapsed: true })

    expect(screen.queryByText('Recent')).not.toBeInTheDocument()
    expect(screen.queryByText('No conversations yet')).not.toBeInTheDocument()
  })

  it('shows empty state silently on 400 error (no error text)', async () => {
    server.use(
      http.get(`${BASE_URL}/${ENDPOINTS.CHATS}`, () =>
        HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'Missing cookie', details: {} } },
          { status: 400 },
        ),
      ),
    )

    renderSidebar()

    expect(await screen.findByText('No conversations yet')).toBeInTheDocument()
    expect(screen.queryByText(/error/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Missing cookie/i)).not.toBeInTheDocument()
  })
})
