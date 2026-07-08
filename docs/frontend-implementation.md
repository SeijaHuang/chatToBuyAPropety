# Frontend Implementation

| Field | Value |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript 5 (strict mode) |
| Styling | Tailwind CSS 4 (CSS-first, `@theme` in globals) |
| State | Zustand 4 (TanStack Query 5 installed for P1, not yet wired) |
| HTTP | Axios 1 — `lib/request.ts` (transport, cookie-based session via `withCredentials`), `services/` (domain calls) |
| Testing | Vitest 2 + Testing Library + MSW 2 |
| Package manager | pnpm |

---

## Architecture Overview

### Page → Component → Store → Service flow

```
/                           (main)/page.tsx
                                │ first message → router.push /chat/new?q=…
                                │ (no client-side sessionId — backend assigns it)
                                │
/chat/:sessionId            (main)/chat/[sessionId]/page.tsx
                                │ renders <ChatSession sessionId initialMessage>
                                │ sessionId === 'new' is a sentinel for "not yet created"
                                │
                        ChatSession (container)
                                │ useSession(sessionId, enabled=!isNewSession) — DB fetch-or-fresh
                                │ useChat()              — sendMessage, isLoading, errorMessage
                                │ useConversationStore   — messages, state, routing
                                │
                        ChatInput (UI)     ChatMessage (UI)    BorrowingCapacityCard (UI)
                                                               BudgetGapCard (UI)
                                │
                        services/chat.ts    → POST api/v1/chat        (create/continue turn)
                                            → GET  api/v1/chat/:id     (restore a session)
                                            → GET  api/v1/chats       (sidebar history list)
                        services/summary.ts → POST api/v1/chat/summary
```

```
SideNavBar (container)
    │ useChatHistory()  → GET api/v1/chats → top 10 ChatSessionDTO
    │
    ChatHistoryList (container) — renders "Recent" list, active-session highlight,
                                   relative-time labels, intent-derived titles
```

### Routing

The app uses Next.js App Router with a route group `(main)` that wraps all pages in `LayoutShell`. There is no client-generated session ID: the landing page navigates straight to the literal route `/chat/new?q=<message>`. `ChatSession` treats `sessionId === 'new'` as a sentinel — it skips the DB fetch, sends the initial message with `sessionId: null`, and the backend creates the row and returns the real UUID in the response. `useChat.sendMessage` then calls `router.replace('/chat/:realSessionId')` so the URL and the DB agree. `uuid` (the npm package) is only used client-side now, to generate `UIMessage.id` values — never session IDs.

### State persistence — DB-backed, not sessionStorage

Session state is no longer mirrored to `sessionStorage`. The database is the single source of truth:

| Action | Endpoint | Effect |
|---|---|---|
| Continue an existing session | `POST api/v1/chat` (`sessionId` set) | Backend upserts the turn; response `state` (a `ConversationSnapshotDTO`) fully replaces the store's `state` |
| Start a new session | `POST api/v1/chat` (`sessionId: null`) | Backend creates the anonymous user (via cookie) + session row, returns a fresh `sessionId` |
| Reload / revisit a session URL | `GET api/v1/chat/:sessionId` (`useSession`) | `200` → `restoreSession(response)`: if `conversationHistory` is non-empty (Redis hit) splits it into `UIMessage[]`; if empty and `resumeMessage` is non-null (Postgres fallback restore — Redis key had expired) renders that single string as the first assistant message instead; either way replays any collected cards. `404`/error → falls back to `initSession` (blank local state, no backend write) |
| Populate the sidebar | `GET api/v1/chats` (`useChatHistory`) | Returns up to 10 `ChatSessionDTO` summaries for the current anonymous identity (cookie-scoped) |

Anonymous identity is carried by an httpOnly cookie; `axiosClient` sets `withCredentials: true` so every request includes it. `constants/storageKeys.ts` (`CONVERSATION_STATE_PREFIX`, `ROUTING_PAYLOAD_PREFIX`) is legacy from the pre-DB implementation and is currently unused — do not add new sessionStorage writes without revisiting this.

---

## Source File Map

```
frontend/src/
├── app/
│   ├── layout.tsx                Root layout — loads Plus Jakarta Sans via next/font,
│   │                             injects --font-plus-jakarta-sans CSS variable into <html>
│   └── (main)/
│       ├── layout.tsx            Route-group layout — wraps all (main) pages in <LayoutShell>
│       ├── page.tsx              Landing/home page — hero ChatInput; on first send, pushes
│       │                         to /chat/new?q=… (no client-generated sessionId)
│       └── chat/
│           └── [sessionId]/
│               └── page.tsx      Chat session page — renders <ChatSession>; passes sessionId
│                                 (may be literal "new") and searchParams.q as initialMessage
│
├── styles/
│   └── globals.css               Tailwind CSS v4 design system — @theme tokens (colors,
│                                 typography, spacing, radius, shadows, blur), :root glass/glow
│                                 vars, @layer base (body, type scale, scrollbar, Material Symbols),
│                                 @layer utilities (glass-panel, glass-ai)
│
├── constants/                    App-wide as-const value objects; never use magic strings elsewhere
│   ├── index.ts                  Barrel — re-exports all constants
│   ├── conversation.ts           MESSAGE_ROLE, MODULE_ID, SESSION_STATUS, SUBMODEL_KEY
│   ├── routing.ts                USER_INTENT, EXECUTION_MODE, TRIGGER_SOURCE
│   ├── ui.ts                     COMPONENT_SIZE, COMPONENT_VARIANT, COMPONENT_COLOR
│   ├── storageKeys.ts            STORAGE_KEY — sessionStorage key prefixes; currently unused
│   │                             (superseded by DB-backed persistence — kept for P1 routing handoff)
│   ├── endpoints.ts              ENDPOINTS — API path constants (CHAT, CHAT_SUMMARY, CHATS, HEALTH)
│   └── errorCodes.ts             ERROR_CODE / ERROR_MESSAGE — normalised error identifiers
│
├── lib/
│   ├── request.ts                Axios instance (baseURL, withCredentials: true for the anonymous
│   │                             session cookie, timeout, headers) + request interceptor
│   │                             + normalizeError helper + exported request.post / request.get;
│   │                             do not import this directly from components or hooks
│   ├── utils.ts                  cn() (clsx + tailwind-merge), createInitialState(), formatAUD(),
│   │                             formatRelativeTime() ("just now" / "5 minutes ago" / "3 days ago")
│   └── tv.ts                     Custom tv() instance via createTV() — extends twMerge config
│                                 to classify @theme text-size tokens as font-size (not color)
│                                 so text-label-lg/body-md etc. don't conflict with text-primary
│
├── services/                     Domain-level API calls — one file per backend resource
│   ├── index.ts                  Barrel — re-exports public surface of all service files
│   ├── chat.ts                   postChat(message, sessionId | null) → POST api/v1/chat;
│   │                             getSession(sessionId) → GET api/v1/chat/:sessionId (restore);
│   │                             getChats() → GET api/v1/chats (sidebar history)
│   └── summary.ts                postChatSummary(collectedData, sessionId, intent?)
│                                 → POST api/v1/chat/summary
│
├── stores/                       Zustand stores — one file per domain concern
│   ├── index.ts                  Barrel — re-exports useConversationStore, useUIStore
│   ├── conversationStore.ts      useConversationStore — sessionId, state (ConversationSnapshotDTO
│   │                             | null — no conversationHistory), messages (UIMessage[]), routing,
│   │                             isLoading; actions: initSession (blank local state),
│   │                             setUpdatedState (full replacement, no storage side effect),
│   │                             setSessionFromResponse (promotes a "new" session to its real ID +
│   │                             state once the backend responds), restoreSession (hydrates from a
│   │                             SessionRestoreResponse fetched via GET: splits conversationHistory
│   │                             into messages on a Redis hit, or renders resumeMessage as the sole
│   │                             assistant message on a Postgres fallback restore; replays cards
│   │                             either way), addUserMessage, addAssistantMessage, setAssistantLoading,
│   │                             setLoading, setRouting, clearSession
│   └── uiStore.ts                useUIStore — sidebarCollapsed, activeModal;
│                                 actions: toggleSidebar, setSidebarCollapsed, openModal, closeModal
│
├── hooks/                        React hooks — one responsibility each
│   ├── index.ts                  Barrel — re-exports useChat, useSession, useChatHistory
│   ├── useChat.ts                sendMessage, isLoading, errorMessage, clearError; determines
│   │                             new-vs-continuing session from store.sessionId, posts with
│   │                             sessionId: null when new, promotes via setSessionFromResponse +
│   │                             router.replace on success; maps API error codes to user-facing
│   │                             messages
│   ├── useSession.ts             useSession(sessionId, enabled = true) → { isRestored, isLoading };
│   │                             when enabled, GETs the session from the DB — success calls
│   │                             restoreSession, failure falls back to initSession (fresh local
│   │                             state, no backend write)
│   └── useChatHistory.ts         useChatHistory() → { sessions: ChatSessionDTO[], isLoading };
│                                 fetches getChats() on mount, keeps top 10, silently empties on
│                                 error or missing session cookie
│
├── components/                   UI and feature components
│   ├── index.ts                  Barrel — re-exports domain components
│   ├── shared/                   Generic UI atoms — no store reads, no hooks, no side effects
│   │   ├── index.ts              Barrel — Button, Chip, AIBadge, Skeleton*, MaterialSymbol, TypingIndicator
│   │   ├── Button.tsx            Multi-variant button (primary/secondary/ghost/danger) with
│   │   │                         optional icon and loading spinner
│   │   ├── Chip.tsx              Label chip with optional icon and remove button
│   │   ├── AIBadge.tsx           Glass badge with AI icon; sizes sm | md
│   │   ├── Skeleton.tsx          SkeletonText and SkeletonMessage loading placeholders
│   │   ├── MaterialSymbol.tsx    Thin wrapper for Material Symbols icon font
│   │   └── TypingIndicator.tsx   Three-dot animated typing indicator
│   ├── layout/                   App chrome — container components that read from stores
│   │   ├── index.ts              Barrel — re-exports LayoutShell, TopNavBar, SideNavBar,
│   │   │                         BottomNavBar, ChatHistoryList
│   │   ├── LayoutShell.tsx       Root layout container — composes SideNavBar + TopNavBar +
│   │   │                         main slot + BottomNavBar; applies sidebar offset transition
│   │   ├── TopNavBar.tsx         Top application bar — branding and top-level actions
│   │   ├── SideNavBar.tsx        Collapsible side navigation; receives collapsed +
│   │   │                         onToggleCollapse + activePath as props; owns "New Chat"
│   │   │                         (clearSession + navigate to "/") and renders ChatHistoryList
│   │   ├── BottomNavBar.tsx      Mobile bottom navigation bar — shown below md breakpoint
│   │   └── ChatHistoryList.tsx   "Recent" sidebar list — useChatHistory(); skeleton while
│   │                             loading, empty state, active-session highlight via activePath,
│   │                             intent-derived title (INTENT_LABELS map), formatRelativeTime()
│   └── chat/                     Chat-domain feature components (flat files, one barrel)
│       ├── index.ts              Barrel — re-exports all six chat components
│       ├── ChatSession.tsx       Top-level chat container — owns useSession + useChat;
│       │                         renders message list, fixed ChatInput footer, error alert,
│       │                         and post-completion CTA; auto-scrolls; treats sessionId === 'new'
│       │                         as "not yet created" (skips restore, fires initialMessage once)
│       ├── ChatInput.tsx         Textarea + send button; fires onSend(trimmedMessage)
│       ├── ChatMessage.tsx       Renders user / assistant message bubble; embeds result cards
│       ├── ModuleProgress.tsx    Sticky step-progress bar (M1→M4)
│       ├── ModuleStep.tsx        Internal step indicator used only by ModuleProgress
│       ├── BorrowingCapacityCard.tsx  Displays BorrowingCapacityResult; disclaimer always rendered
│       └── BudgetGapCard.tsx     Displays BudgetGapResult; returns null when has_gap is false
│
├── stories/                       Ladle stories — mirrors component structure (see coding-standards.md)
│   ├── shared/                    AIBadge, Button, Chip, Skeleton, TypingIndicator stories
│   ├── BorrowingCapacityCard.stories.tsx
│   ├── BudgetGapCard.stories.tsx
│   ├── ChatInput.stories.tsx
│   ├── ChatMessage.stories.tsx
│   └── ModuleProgress.stories.tsx
│
├── types/                         All type files end with .d.ts — mirrors backend models/ layout
│   ├── index.d.ts                 Barrel — re-exports public surface of all type files
│   ├── conversation.d.ts          Domain enums (MODULE_ID, SESSION_STATUS, SUBMODEL_KEY,
│   │                              MESSAGE_ROLE), M1–M4 sub-model interfaces, CollectedData,
│   │                              ConversationStateDTO (full, incl. conversationHistory),
│   │                              ConversationSnapshotDTO (Omit<…, 'conversationHistory'> — what
│   │                              POST /chat returns on every turn), UIMessage
│   ├── api.d.ts                   HTTP contract: APIResponse<TData>, ChatResponse (now includes
│   │                              sessionId), SummaryResponse, ChatSessionDTO (sidebar list item:
│   │                              sessionId, status, initialIntent, createdAt, updatedAt,
│   │                              completedAt), SessionRestoreResponse (GET /chat/:sessionId
│   │                              response — resumeMessage, state, conversationHistory),
│   │                              ErrorDetail, ErrorResponse, SuccessResponse
│   ├── financial.d.ts             BorrowingCapacityResult, BudgetGapResult
│   │                              (snake_case — backend @dataclass bypasses camelCase alias)
│   ├── userNeeds.d.ts             UserNeeds interface (mirrors backend models/user_needs.py)
│   ├── routing.d.ts               USER_INTENT, EXECUTION_MODE, TRIGGER_SOURCE as const objects,
│   │                              derived union types, RoutingPayload interface
│   ├── ui.d.ts                    ComponentSize, ComponentVariant, ComponentColor
│   │                              (derived from constants/ui.ts via typeof)
│   └── global.d.ts                Ambient global type declarations
│
└── __tests__/                     Vitest tests — mirrors src/ structure
    ├── msw/
    │   ├── server.ts               MSW node server (onUnhandledRequest: 'error')
    │   ├── handlers.ts             Shared happy-path HTTP handlers (chat, session GET, chats GET)
    │   └── fixtures.ts             Shared mock payloads (mockSnapshot, mockChatResponse,
    │                              mockChatSessions, mockConversationState, …) imported by handlers
    ├── lib/
    │   ├── request.test.ts
    │   └── utils.test.ts
    ├── stores/
    │   ├── conversationStore.test.ts
    │   └── uiStore.test.ts
    ├── hooks/
    │   ├── useChat.test.ts
    │   ├── useSession.test.ts
    │   └── useChatHistory.test.ts
    ├── services/
    │   ├── chat.test.ts
    │   └── summary.test.ts
    └── components/
        ├── chat/
        │   ├── BorrowingCapacityCard.test.tsx
        │   ├── BudgetGapCard.test.tsx
        │   ├── ChatInput.test.tsx
        │   ├── ChatMessage.test.tsx
        │   ├── ModuleProgress.test.tsx
        │   └── ChatSession.test.tsx
        ├── shared/
        │   ├── AIBadge.test.tsx
        │   ├── Button.test.tsx
        │   ├── Chip.test.tsx
        │   └── Skeleton.test.tsx
        └── layout/
            └── SideNavBar.test.tsx
```

---

## Data Flow — Single Chat Turn

```
User types → ChatInput.onSend(content)
    │
    ▼
useChat.sendMessage(content)
    ├── isNewSession = store.sessionId === null || store.sessionId === 'new'
    ├── store.addUserMessage(content)          — appends user bubble
    ├── store.setAssistantLoading(true)        — appends placeholder bubble
    ├── postChat(content, isNewSession ? null : store.sessionId)  — POST /api/v1/chat
    │       └── services/chat.ts → lib/request.ts → axios (withCredentials) → backend
    │
    ├── [success]
    │   ├── store.addAssistantMessage(reply)   — replaces placeholder with reply
    │   ├── [isNewSession]
    │   │       store.setSessionFromResponse(sessionId, state)  — adopts the real ID
    │   │       router.replace(`/chat/${sessionId}`)            — syncs the URL
    │   ├── [continuing]
    │   │       store.setUpdatedState(state)   — full ConversationSnapshotDTO replacement
    │   │       ├── injects BorrowingCapacityCard if borrowingCapacity newly non-null
    │   │       └── injects BudgetGapCard if budgetGap.has_gap is true
    │   └── store.setRouting(routing)          — if non-null (requirements complete)
    │
    └── [error]
        └── setErrorMessage(user-facing string)
```

### Session restore (reload / revisit)

```
ChatSession mounts with sessionId
    │
    ├── sessionId === 'new'  → clearSession(); wait for initialMessage to fire sendMessage
    │
    └── sessionId !== 'new'  → useSession(sessionId, enabled: true)
            └── GET api/v1/chat/:sessionId
                    ├── [200] restoreSession(response)
                    │           — conversationHistory non-empty (Redis hit): splits into UIMessage[]
                    │           — conversationHistory empty + resumeMessage non-null (Postgres
                    │             fallback restore): renders resumeMessage as the sole assistant message
                    │           — replays borrowingCapacity / budgetGap cards either way
                    └── [404 / error] initSession(sessionId) — blank local state, no backend write
```

### Sidebar chat history

```
SideNavBar renders ChatHistoryList (when expanded)
    │
    ▼
useChatHistory() → GET api/v1/chats → top 10 ChatSessionDTO, newest first
    ├── [loading]  three SkeletonText rows
    ├── [empty / 400 missing cookie / network error]  "No conversations yet"
    └── [populated]  one row per session — label from INTENT_LABELS[initialIntent],
                     relative time via formatRelativeTime(updatedAt),
                     highlighted when activePath === `/chat/${session.sessionId}`
```

---

## Key Invariants

| # | Invariant | File |
|---|---|---|
| 1 | `setUpdatedState` / `setSessionFromResponse` / `restoreSession` do a full state replacement, never spread/merge | `conversationStore.ts` |
| 2 | No magic domain strings — use constants from `@/constants` | `constants/*.ts` |
| 3 | No axios/fetch in components or hooks — all HTTP through `services/` | `services/*.ts` |
| 4 | `BorrowingCapacityCard` must always render `data.disclaimer` | `BorrowingCapacityCard.tsx` |
| 5 | Financial types (`BorrowingCapacityResult`, `BudgetGapResult`) are snake_case | `types/financial.d.ts` |
| 6 | Domain optional fields use `T \| null`, not `T \| undefined` | `types/conversation.d.ts` |
| 7 | Theme tokens only — no Tailwind built-in color/size values | `globals.css` + all components |
| 8 | All component variants defined with `tv()` from `lib/tv.ts` | shared components |
| 9 | List keys are stable IDs, never array indices | `ChatSession.tsx`, `ChatHistoryList.tsx` |
| 10 | `'use client'` pushed to leaf components; layouts and pages default to Server Components | `app/(main)/` |
| 11 | Session state is DB-backed, not `sessionStorage` — `"new"` is the only client-side session sentinel | `conversationStore.ts`, `useSession.ts` |

---

## Coverage Targets

| Module | Target |
|---|---|
| `src/lib/utils.ts` | 100% |
| `src/lib/request.ts` | ≥ 80% |
| `src/stores/*.ts` | ≥ 80% |
| `src/hooks/*.ts` | ≥ 80% |
| `src/services/*.ts` | ≥ 80% |
| `src/components/**/*.tsx` | ≥ 80% |

---

## Dev Commands

All commands run from `frontend/`:

```bash
pnpm dev            # start dev server (localhost:3000)
pnpm build          # production build + type check
pnpm lint           # ESLint
pnpm type-check     # tsc --noEmit
pnpm test           # vitest watch mode
pnpm test:run       # vitest single run
pnpm test:coverage  # vitest run --coverage
pnpm ladle          # component explorer (localhost:61000)
```
