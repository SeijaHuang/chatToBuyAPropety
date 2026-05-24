# Frontend Testing

## Coverage Requirements

| Module | Minimum coverage |
|---|---|
| `src/lib/utils.ts` | 100% |
| `src/stores/*.ts` | ≥ 80% |
| `src/hooks/*.ts` | ≥ 80% |
| `src/lib/api.ts` | ≥ 80% |
| `src/lib/request.ts` | ≥ 80% |
| `src/components/**/*.tsx` | ≥ 80% |

## Rules

- Test files live in `src/__tests__/`, mirroring the source tree structure: `src/__tests__/hooks/useChat.test.ts` tests `src/hooks/useChat.ts`.
- Every test file opens with a `describe` block named after the source unit (component, hook, or function name). No verbs.
- Test function names: `it('<behaviour under test>')` in plain English describing the expected behaviour from a user perspective.
- Each test tests one behaviour. Do not combine assertions for unrelated scenarios in a single `it` block.
- API calls in tests must be intercepted with MSW handlers; no live network requests in the test suite.
- Never import from `lib/request.ts` directly in tests — mock at the MSW handler level so the full `lib/api.ts` path is exercised.
- Snapshot tests are forbidden. Test behaviour and output, not HTML structure.

## Test File Layout

```
src/
├── __tests__/
│   ├── components/
│   │   └── ChatInput.test.tsx
│   ├── hooks/
│   │   └── useChat.test.ts
│   ├── stores/
│   │   └── conversationStore.test.ts
│   ├── lib/
│   │   └── api.test.ts
│   └── msw/
│       ├── handlers.ts
│       └── server.ts
├── components/
├── hooks/
├── stores/
└── lib/
```

## MSW Setup

### Server lifecycle

Define the MSW server in `src/__tests__/msw/server.ts` and wire its lifecycle in `vitest.setup.ts`. The `onUnhandledRequest: 'error'` flag forces every real request to have a handler — unmatched requests fail the test immediately.

```ts
// src/__tests__/msw/server.ts
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

```ts
// vitest.setup.ts
import '@testing-library/jest-dom'
import { beforeAll, afterEach, afterAll } from 'vitest'
import { server } from '@/__tests__/msw/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

### Shared handlers

Define reusable happy-path handlers in `src/__tests__/msw/handlers.ts`. Override per-test with `server.use(...)` for error or edge-case scenarios; `afterEach` resets them automatically.

```ts
// src/__tests__/msw/handlers.ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.post('http://localhost:8000/api/v1/chat', () =>
    HttpResponse.json({ reply: 'mock reply', currentModule: 'M1_PROPERTY_NEEDS' })
  ),
]
```

```ts
// per-test override for error path
it('shows an error message when the API returns 500', async () => {
  server.use(
    http.post('http://localhost:8000/api/v1/chat', () =>
      HttpResponse.json({ error: { code: 'INTERNAL', message: 'fail' } }, { status: 500 })
    )
  )
  // ...
})
```

## Tool Usage by Layer

| Layer | Tool |
|---|---|
| Component rendering + user interaction | `@testing-library/react` (`render`, `screen`, `userEvent`) |
| Hook isolation | `renderHook` from `@testing-library/react` |
| API interception | MSW only — never `vi.mock` for HTTP |
| Third-party module mocking | `vi.mock` (e.g. `next/navigation`, `next/router`) |
| Zustand store | Import and call actions directly; reset in `beforeEach` with `useStore.setState(initialState)` |
| Timers / async | `vi.useFakeTimers()` + `vi.runAllTimersAsync()`; restore in `afterEach` |

## `vi.mock` vs MSW

| Scenario | Tool |
|---|---|
| Intercepting HTTP requests | MSW — always |
| Mocking third-party libraries (`next/navigation`, `next/router`) | `vi.mock` |
| Mocking internal project modules | `vi.mock` only if the dependency cannot be injected via props |

Never use `vi.mock` to intercept HTTP — it bypasses `lib/api.ts` and leaves the actual request path untested.

```ts
// ✓ third-party module mock
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

// ✗ HTTP mock via vi.mock — use MSW instead
vi.mock('@/lib/api', () => ({
  sendMessage: vi.fn().mockResolvedValue({ reply: 'mock' }),
}))
```

## User Interaction — `userEvent` over `fireEvent`

Always use `userEvent` from `@testing-library/user-event`. Never use `fireEvent`.

`fireEvent` dispatches a single synthetic DOM event. `userEvent` simulates the full browser interaction chain (focus → keydown → input → keyup → blur), catching bugs that `fireEvent` misses.

```ts
// ✓
const user = userEvent.setup()
await user.type(screen.getByRole('textbox'), 'hello')
await user.click(screen.getByRole('button', { name: /send/i }))

// ✗
fireEvent.change(screen.getByRole('textbox'), { target: { value: 'hello' } })
fireEvent.click(screen.getByRole('button', { name: /send/i }))
```

## Async Query Rules

Use the right query for the timing of the element:

| Situation | Query |
|---|---|
| Element is already in the DOM | `getBy*` |
| Element appears after async work | `findBy*` (has built-in `waitFor`) |
| Waiting for a side effect, not an element | `waitFor(() => expect(...))` |

```ts
// ✓ element already present
expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()

// ✓ element appears after API response
const reply = await screen.findByText('mock reply')
expect(reply).toBeVisible()

// ✓ waiting for a callback to have been called
await waitFor(() => expect(onSend).toHaveBeenCalledOnce())

// ✗ redundant waitFor wrapping findBy
await waitFor(() => screen.findByText('mock reply'))
```

## UI vs Container Test Strategy

Matches the UI/Container separation in [coding-standards.md](coding-standards.md).

**UI components** — render with props only. No store, no MSW. Assert on what the user sees.

```ts
describe('MessageBubble', () => {
  it('shows typing indicator when isLoading is true', () => {
    render(<MessageBubble content="" role="assistant" isLoading={true} />)
    expect(screen.getByTestId('typing-indicator')).toBeVisible()
  })

  it('renders content when not loading', () => {
    render(<MessageBubble content="Hello" role="assistant" isLoading={false} />)
    expect(screen.getByText('Hello')).toBeVisible()
  })
})
```

**Container components** — wire up MSW + store reset. Test the full user interaction flow.

```ts
describe('MessageList', () => {
  beforeEach(() => {
    useConversationStore.setState(initialConversationState)
  })

  it('appends assistant reply after user sends a message', async () => {
    const user = userEvent.setup()
    render(<MessageList />)
    await user.type(screen.getByRole('textbox'), 'hello')
    await user.click(screen.getByRole('button', { name: /send/i }))
    expect(await screen.findByText('mock reply')).toBeVisible()
  })
})
```

## `describe` Block Convention

Every test file has exactly one top-level `describe` block named after the source unit. Nested `describe` blocks are allowed for grouping related scenarios, but must not exceed two levels deep.

```ts
// ✓
describe('useChat', () => {
  describe('sendMessage', () => {
    it('appends user message to store', ...)
    it('sets isLoading during request', ...)
  })

  describe('clearSession', () => {
    it('resets messages and sessionId', ...)
  })
})

// ✗ no top-level describe
it('appends user message to store', ...)

// ✗ three levels deep
describe('useChat', () => {
  describe('sendMessage', () => {
    describe('on success', () => { ... })
  })
})
```

## Hook Tests

Use `renderHook` with a wrapper that provides any required context (Zustand store, React Query client).

```ts
describe('useChat', () => {
  beforeEach(() => {
    useConversationStore.setState(initialConversationState)
  })

  it('appends a user message to the store on sendMessage', async () => {
    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('hello')
    })
    expect(useConversationStore.getState().messages).toHaveLength(1)
  })
})
```

## `data-testid` Convention

Use `data-testid` only when no accessible role, label, or visible text query can uniquely identify the element. See [coding-standards.md](coding-standards.md) for the attribute naming convention.

Prefer accessible queries in this order:

1. `getByRole` — most resilient, tests accessibility implicitly
2. `getByLabelText` — for form fields
3. `getByText` — for visible content
4. `getByTestId` — last resort only
