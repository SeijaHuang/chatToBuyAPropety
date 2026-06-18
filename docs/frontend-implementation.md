# Frontend Implementation

| Field | Value |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript 5 (strict mode) |
| Styling | Tailwind CSS 4 (CSS-first, `@theme` in globals) |
| State | Zustand 4 |
| HTTP | Axios 1 — `lib/request.ts` (transport), `services/` (domain calls) |
| Testing | Vitest 2 + Testing Library + MSW 2 |
| Package manager | pnpm |

---

## Architecture Overview

### Page → Component → Store → Service flow

```
/                           (main)/page.tsx
                                │ first message → uuid sessionId → router.push /chat/:id?q=…
                                │
/chat/:sessionId            (main)/chat/[sessionId]/page.tsx
                                │ renders <ChatSession sessionId initialMessage>
                                │
                        ChatSession (container)
                                │ useSession(sessionId)  — restore or init
                                │ useChat()              — sendMessage, isLoading, errorMessage
                                │ useConversationStore   — messages, state, routing
                                │
                        ChatInput (UI)     ChatMessage (UI)    BorrowingCapacityCard (UI)
                                                               BudgetGapCard (UI)
                                │
                        services/chat.ts → POST /api/v1/chat
                        services/summary.ts → POST /api/v1/chat/summary
```

### Routing

The app uses Next.js App Router with a route group `(main)` that wraps all pages in `LayoutShell`. Session IDs are UUIDs generated on the landing page and embedded in the URL.

### State persistence

`conversationStore` mirrors `ConversationStateDTO` to `sessionStorage` on every update using the key `conversation_state_<sessionId>`. On navigation back to an existing session, `useSession` restores state from storage and reconstructs the message list from `conversationHistory`.

---

## Source File Map

```
frontend/src/
├── app/
│   ├── layout.tsx                Root layout — loads Plus Jakarta Sans via next/font,
│   │                             injects --font-plus-jakarta-sans CSS variable into <html>
│   └── (main)/
│       ├── layout.tsx            Route-group layout — wraps all (main) pages in <LayoutShell>
│       ├── page.tsx              Landing/home page — renders hero ChatInput; on first send,
│       │                         generates uuid sessionId and navigates to /chat/:id?q=…
│       └── chat/
│           └── [sessionId]/
│               └── page.tsx      Chat session page — renders <ChatSession>; passes sessionId
│                                 and searchParams.q as initialMessage
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
│   ├── storageKeys.ts            STORAGE_KEY — sessionStorage key prefixes
│   │                             (CONVERSATION_STATE_PREFIX, ROUTING_PAYLOAD_PREFIX)
│   ├── endpoints.ts              ENDPOINTS — API path constants (CHAT, CHAT_SUMMARY, HEALTH)
│   └── errorCodes.ts             ERROR_CODE / ERROR_MESSAGE — normalised error identifiers
│
├── lib/
│   ├── request.ts                Axios instance (baseURL, timeout, headers) + request interceptor
│   │                             + normalizeError helper + exported request.post / request.get;
│   │                             do not import this directly from components or hooks
│   ├── utils.ts                  cn() (clsx + tailwind-merge), createInitialState(),
│   │                             formatAUD() and other pure utility functions
│   └── tv.ts                     Custom tv() instance via createTV() — extends twMerge config
│                                 to classify @theme text-size tokens as font-size (not color)
│                                 so text-label-lg/body-md etc. don't conflict with text-primary
│
├── services/                     Domain-level API calls — one file per backend resource
│   ├── index.ts                  Barrel — re-exports public surface of all service files
│   ├── chat.ts                   postChat(message, sessionId) → POST api/v1/chat
│   └── summary.ts                postChatSummary(collectedData, sessionId, intent?)
│                                 → POST api/v1/chat/summary
│
├── stores/                       Zustand stores — one file per domain concern
│   ├── index.ts                  Barrel — re-exports useConversationStore, useUIStore
│   ├── conversationStore.ts      useConversationStore — sessionId, state (ConversationStateDTO),
│   │                             messages (UIMessage[]), routing, isLoading;
│   │                             actions: initSession, setUpdatedState (full replacement +
│   │                             sessionStorage sync + card injection), addUserMessage,
│   │                             addAssistantMessage, setAssistantLoading, setLoading,
│   │                             setRouting, restoreFromStorage, clearSession
│   └── uiStore.ts                useUIStore — sidebarCollapsed, activeModal;
│                                 actions: toggleSidebar, setSidebarCollapsed, openModal, closeModal
│
├── hooks/                        React hooks — one responsibility each
│   ├── index.ts                  Barrel — re-exports useChat, useSession
│   ├── useChat.ts                sendMessage, isLoading, errorMessage, clearError;
│   │                             orchestrates store mutations and postChat call;
│   │                             maps API error codes to user-facing messages
│   └── useSession.ts             useSession(sessionId) → { isRestored };
│                                 on mount: attempts restoreFromStorage, falls back to initSession
│
├── types/                        All type files end with .d.ts — mirrors backend models/ layout
│   ├── index.d.ts                Barrel — re-exports public surface of all type files
│   ├── conversation.d.ts         Domain enums (MODULE_ID, SESSION_STATUS, SUBMODEL_KEY,
│   │                             MESSAGE_ROLE), M1–M4 sub-model interfaces, CollectedData,
│   │                             ConversationStateDTO, UIMessage
│   ├── api.d.ts                  HTTP contract: APIResponse<TData>, ChatResponse,
│   │                             SummaryResponse, ErrorDetail, ErrorResponse, SuccessResponse
│   ├── financial.d.ts            BorrowingCapacityResult, BudgetGapResult
│   │                             (snake_case — backend @dataclass bypasses camelCase alias)
│   ├── user_needs.d.ts           UserNeeds interface (mirrors backend models/user_needs.py)
│   ├── routing.d.ts              USER_INTENT, EXECUTION_MODE, TRIGGER_SOURCE as const objects,
│   │                             derived union types, RoutingPayload interface
│   ├── ui.d.ts                   ComponentSize, ComponentVariant, ComponentColor
│   │                             (derived from constants/ui.ts via typeof)
│   └── global.d.ts               Ambient global type declarations
│
├── components/
│   ├── index.ts                  Barrel — re-exports domain components
│   │
│   ├── shared/                   Generic UI atoms — no store reads, no hooks, no side effects
│   │   ├── index.ts              Barrel — Button, Chip, AIBadge, Skeleton*, MaterialSymbol,
│   │   │                         TypingIndicator
│   │   ├── Button.tsx            Multi-variant button (primary/secondary/ghost/danger) with
│   │   │                         optional icon and loading spinner
│   │   ├── Chip.tsx              Label chip with optional icon and remove button
│   │   ├── AIBadge.tsx           Glass badge with AI icon; sizes sm | md
│   │   ├── Skeleton.tsx          SkeletonText and SkeletonMessage loading placeholders
│   │   ├── MaterialSymbol.tsx    Thin wrapper for Material Symbols icon font
│   │   └── TypingIndicator.tsx   Three-dot animated typing indicator
│   │
│   ├── layout/                   App chrome — container components that read from UIStore
│   │   ├── index.ts              Barrel — re-exports LayoutShell, TopNavBar, SideNavBar,
│   │   │                         BottomNavBar
│   │   ├── LayoutShell.tsx       Root layout container — composes SideNavBar + TopNavBar +
│   │   │                         main slot + BottomNavBar; applies sidebar offset transition
│   │   ├── TopNavBar.tsx         Top application bar — branding and top-level actions
│   │   ├── SideNavBar.tsx        Collapsible side navigation; receives collapsed + onToggleCollapse
│   │   │                         + activePath as props
│   │   └── BottomNavBar.tsx      Mobile bottom navigation bar — shown below md breakpoint
│   │
│   ├── ChatSession/              Top-level chat container component
│   │   ├── index.ts              Barrel
│   │   └── ChatSession.tsx       Container — owns useSession + useChat; renders message list,
│   │                             fixed ChatInput footer, error alert, and post-completion CTA;
│   │                             auto-scrolls to bottom on new messages; fires initialMessage
│   │                             on first render when provided via searchParams
│   │
│   ├── ChatInput/                Textarea + send button; fires onSend(trimmedMessage)
│   │   ├── index.ts
│   │   └── ChatInput.tsx
│   │
│   ├── ChatMessage/              Renders user / assistant message bubble; embeds result cards
│   │   ├── index.ts
│   │   └── ChatMessage.tsx
│   │
│   ├── ModuleProgress/           Sticky step-progress bar (M1→M4); ModuleStep is internal
│   │   ├── index.ts
│   │   ├── ModuleProgress.tsx
│   │   └── ModuleStep.tsx
│   │
│   ├── BorrowingCapacityCard/    Displays BorrowingCapacityResult; disclaimer always rendered
│   │   ├── index.ts
│   │   └── BorrowingCapacityCard.tsx
│   │
│   └── BudgetGapCard/            Displays BudgetGapResult; returns null when has_gap is false
│       ├── index.ts
│       └── BudgetGapCard.tsx
│
└── __tests__/                    Vitest tests — mirrors src/ structure
    ├── msw/
    │   ├── server.ts             MSW node server (onUnhandledRequest: 'error')
    │   └── handlers.ts           Shared happy-path HTTP handlers
    ├── lib/
    │   ├── request.test.ts
    │   └── utils.test.ts
    ├── stores/
    │   ├── conversationStore.test.ts
    │   └── uiStore.test.ts
    ├── hooks/
    │   ├── useChat.test.ts
    │   └── useSession.test.ts
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
        └── shared/
            ├── AIBadge.test.tsx
            ├── Button.test.tsx
            ├── Chip.test.tsx
            └── Skeleton.test.tsx
```

---

## Data Flow — Single Chat Turn

```
User types → ChatInput.onSend(content)
    │
    ▼
useChat.sendMessage(content)
    ├── store.addUserMessage(content)          — appends user bubble
    ├── store.setAssistantLoading(true)        — appends placeholder bubble
    ├── postChat(content, state.sessionId)     — POST /api/v1/chat
    │       └── services/chat.ts → lib/request.ts → axios → backend
    │
    ├── [success]
    │   ├── store.addAssistantMessage(reply)   — replaces placeholder with reply
    │   ├── store.setUpdatedState(newState)    — full state replacement + sessionStorage sync
    │   │       ├── injects BorrowingCapacityCard if borrowingCapacity newly non-null
    │   │       └── injects BudgetGapCard if budgetGap.has_gap is true
    │   └── store.setRouting(routing)          — if non-null (requirements complete)
    │
    └── [error]
        └── setErrorMessage(user-facing string)
```

### State persistence detail

| Key in sessionStorage | Written when | Read when |
|---|---|---|
| `conversation_state_<sessionId>` | `initSession` (new) and `setUpdatedState` (every turn) | `restoreFromStorage` on page load |
| `routing_payload_<sessionId>` | `ChatSession.handleViewProperties` (P1 handoff) | P2 property-search page (not yet implemented) |

---

## Key Invariants

| # | Invariant | File |
|---|---|---|
| 1 | `setUpdatedState` does a full replacement, never spread/merge | `conversationStore.ts` |
| 2 | No magic domain strings — use constants from `@/constants` | `constants/*.ts` |
| 3 | No axios/fetch in components or hooks — all HTTP through `services/` | `services/*.ts` |
| 4 | `BorrowingCapacityCard` must always render `data.disclaimer` | `BorrowingCapacityCard.tsx` |
| 5 | Financial types (`BorrowingCapacityResult`, `BudgetGapResult`) are snake_case | `types/financial.d.ts` |
| 6 | Domain optional fields use `T \| null`, not `T \| undefined` | `types/conversation.d.ts` |
| 7 | Theme tokens only — no Tailwind built-in color/size values | `globals.css` + all components |
| 8 | All component variants defined with `tv()` from `lib/tv.ts` | shared components |
| 9 | List keys are stable IDs, never array indices | `ChatSession.tsx` |
| 10 | `'use client'` pushed to leaf components; layouts and pages default to Server Components | `app/(main)/` |

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
pnpm dev          # start dev server (localhost:3000)
pnpm build        # production build + type check
pnpm lint         # ESLint
pnpm type-check   # tsc --noEmit
pnpm test         # vitest watch mode
pnpm test:run     # vitest single run
pnpm ladle        # component explorer (localhost:61000)
```
