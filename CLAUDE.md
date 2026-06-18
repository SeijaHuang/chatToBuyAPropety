# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Rules Index

Detailed standards live in `.claude/rules/` — read the relevant file before touching that area:

**Backend (`backend/`)**

| File                                                              | When to read                                                                   |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| [coding-standards.md](.claude/rules/backend/coding-standards.md) | Any time you write or review backend code — naming, types, docstrings, SOLID/DRY/KISS |
| [backend-patterns.md](.claude/rules/backend/backend-patterns.md) | Config, logging, exceptions, API error envelope, prompt placement, null-safety |
| [testing.md](.claude/rules/backend/testing.md)                   | Writing or modifying backend tests — coverage thresholds, mock rules, test naming |

**Frontend (`frontend/`)**

| File                                                               | When to read                                                                         |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| [coding-standards.md](.claude/rules/frontend/coding-standards.md) | Any time you write or review frontend code — naming, types, components, hooks, state |
| [testing.md](.claude/rules/frontend/testing.md)                   | Writing or modifying frontend tests — coverage thresholds, MSW setup, test naming   |

**Shared**

| File                                                 | When to read                                |
| ---------------------------------------------------- | ------------------------------------------- |
| [git-workflow.md](.claude/rules/git-workflow.md)     | Commits, branches, PRs, pre-commit hooks    |

## Frontend Tech Stack

| Layer              | Technology                                      |
| ------------------ | ----------------------------------------------- |
| Framework          | Next.js 14 (App Router)                         |
| Language           | TypeScript 5 (strict mode)                      |
| Styling            | Tailwind CSS 4 (CSS-first, `@theme` in globals) |
| State              | Zustand 4 (client), TanStack Query 5 (P1+)      |
| HTTP               | Axios 1 — `lib/request.ts` (transport), `services/` (domain calls) |
| Testing            | Vitest 2 + Testing Library + MSW 2              |
| Package manager    | pnpm                                            |
| API base URL       | `http://localhost:8000/api/v1` (paths: `chat`, `chat/summary`, no leading `/`) |
| Health endpoint    | `http://localhost:8000/health` (root, no `/api/v1` prefix) |

**Frontend Dev Commands** (run from `frontend/`):

```bash
pnpm dev          # start dev server (localhost:3000)
pnpm build        # production build + type check
pnpm lint         # ESLint
pnpm test         # vitest watch
pnpm test:run     # vitest single run
pnpm type-check   # tsc --noEmit
```

---

## Docs Index

| File                                                                           | Contents                                                                                          |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| [docs/part1-p0-implementation.md](docs/part1-p0-implementation.md)             | Part 1 P0 story completion, E2E criteria, architectural decisions, test coverage                  |
| [docs/frontend-implementation.md](docs/frontend-implementation.md)             | Full frontend source map, data flow, state persistence, component hierarchy, coverage targets     |
| [PRD/PropertyAI_PRD_v1_1.md](PRD/PropertyAI_PRD_v1_1.md)                      | Authoritative PRD v1.1 — P0 stories S-A→S-H, P1 stories §20–26, data models, error handling spec |

---

## Backend Tech Stack

| Layer              | Technology                                    |
| ------------------ | --------------------------------------------- |
| Language           | Python 3.12                                   |
| API framework      | FastAPI                                       |
| Data validation    | Pydantic v2                                   |
| LLM gateway        | OpenRouter API                                |
| Session store      | Redis (P1 — not active in P0)                 |
| Database           | PostgreSQL (JSONB for semi-structured fields) |
| Dependency manager | uv + `pyproject.toml`                         |
| Formatter + Linter | Ruff (line-length 100)                        |
| Type checker       | mypy `--strict`                               |
| Test framework     | pytest (asyncio_mode = auto)                  |
| Logging            | structlog (JSON output)                       |

---

## Backend Development Commands

All commands run from the `backend/` directory. `requirements.txt` mirrors `pyproject.toml` — keep both in sync when adding or removing dependencies.

```bash
# Install with uv (preferred)
uv sync

# Install with pip (fallback)
pip install -r requirements.txt

# Install pre-commit hooks (run once after clone)
uv run pre-commit install

# Dev server
uv run uvicorn main:app --reload --port 8000

# Full test suite with coverage
uv run pytest

# Single test file / single test
uv run pytest tests/test_state_machine.py
uv run pytest tests/test_state_machine.py::test_advance_on_required_fields_collected

# Lint, format check, auto-fix, type check
uv run ruff check .
uv run ruff format --check .
uv run ruff format .
uv run mypy --strict .
```

Infrastructure (Postgres + Redis) from the repo root:

```bash
docker-compose up -d redis postgres
```

---

## Source File Map

Every source file and its single responsibility. Read this before adding code to an existing file or deciding where new code belongs.

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx             Root layout — loads Plus Jakarta Sans via next/font, injects
│   │   │                          --font-plus-jakarta-sans CSS variable into <html>
│   │   └── (main)/
│   │       ├── layout.tsx         Route-group layout — wraps all (main) pages in <LayoutShell>
│   │       ├── page.tsx           Landing/home page — hero ChatInput; first send generates uuid
│   │       │                      sessionId and navigates to /chat/:id?q=…
│   │       └── chat/
│   │           └── [sessionId]/
│   │               └── page.tsx   Chat session page — renders <ChatSession sessionId initialMessage>
│   │
│   ├── styles/
│   │   └── globals.css            Tailwind CSS v4 design system — @theme tokens (colors,
│   │                              typography, spacing, radius, shadows, blur), :root glass/glow
│   │                              vars, @layer base (body, type scale, scrollbar, Material Symbols),
│   │                              @layer utilities (glass-panel, glass-ai)
│   │
│   ├── constants/                 App-wide as-const value objects; never use magic strings elsewhere
│   │   ├── index.ts               Barrel — re-exports all constants
│   │   ├── conversation.ts        MESSAGE_ROLE, MODULE_ID, SESSION_STATUS, SUBMODEL_KEY
│   │   ├── routing.ts             USER_INTENT, EXECUTION_MODE, TRIGGER_SOURCE
│   │   ├── ui.ts                  COMPONENT_SIZE, COMPONENT_VARIANT, COMPONENT_COLOR
│   │   ├── storageKeys.ts         STORAGE_KEY — sessionStorage key prefixes
│   │   │                          (CONVERSATION_STATE_PREFIX, ROUTING_PAYLOAD_PREFIX)
│   │   ├── endpoints.ts           ENDPOINTS — API path constants (CHAT, CHAT_SUMMARY, HEALTH)
│   │   └── errorCodes.ts          ERROR_CODE / ERROR_MESSAGE — normalised error identifiers
│   │
│   ├── lib/
│   │   ├── request.ts             Axios instance (baseURL, timeout, headers) + request interceptor
│   │   │                          + normalizeError helper + exported request.post / request.get;
│   │   │                          do not import this directly from components or hooks
│   │   ├── utils.ts               cn() (clsx + tailwind-merge), createInitialState(),
│   │   │                          formatAUD() and other pure utility functions
│   │   └── tv.ts                  Custom tv() via createTV() — extends twMerge config to classify
│   │                              @theme text-size tokens (text-label-lg, text-body-md…) as
│   │                              font-size so they don't conflict with text-primary color class
│   │
│   ├── services/                  Domain-level API calls — one file per backend resource
│   │   ├── index.ts               Barrel — re-exports public surface of all service files
│   │   ├── chat.ts                postChat(message, sessionId) → POST api/v1/chat
│   │   └── summary.ts             postChatSummary(collectedData, sessionId, intent?)
│   │                              → POST api/v1/chat/summary
│   │
│   ├── stores/                    Zustand stores — one file per domain concern
│   │   ├── index.ts               Barrel — re-exports useConversationStore, useUIStore
│   │   ├── conversationStore.ts   useConversationStore — sessionId, state (ConversationStateDTO),
│   │   │                          messages (UIMessage[]), routing, isLoading; actions: initSession,
│   │   │                          setUpdatedState (full replacement + sessionStorage sync + card
│   │   │                          injection), addUserMessage, addAssistantMessage,
│   │   │                          setAssistantLoading, setLoading, setRouting,
│   │   │                          restoreFromStorage, clearSession
│   │   └── uiStore.ts             useUIStore — sidebarCollapsed, activeModal;
│   │                              actions: toggleSidebar, setSidebarCollapsed, openModal, closeModal
│   │
│   ├── hooks/                     React hooks — one responsibility each
│   │   ├── index.ts               Barrel — re-exports useChat, useSession
│   │   ├── useChat.ts             sendMessage, isLoading, errorMessage, clearError;
│   │   │                          orchestrates store mutations and postChat call;
│   │   │                          maps API error codes to user-facing messages
│   │   └── useSession.ts          useSession(sessionId) → { isRestored };
│   │                              on mount: attempts restoreFromStorage, falls back to initSession
│   │
│   ├── components/                UI and feature components
│   │   ├── index.ts               Barrel — re-exports domain components
│   │   ├── shared/                Generic UI atoms — no store reads, no hooks, no side effects
│   │   │   ├── index.ts           Barrel — Button, Chip, AIBadge, Skeleton*, MaterialSymbol, TypingIndicator
│   │   │   ├── Button.tsx         Multi-variant button (primary/secondary/ghost/danger) with
│   │   │   │                      optional icon and loading spinner
│   │   │   ├── Chip.tsx           Label chip with optional icon and remove button
│   │   │   ├── AIBadge.tsx        Glass badge with AI icon; sizes sm | md
│   │   │   ├── Skeleton.tsx       SkeletonText and SkeletonMessage loading placeholders
│   │   │   ├── MaterialSymbol.tsx Thin wrapper for Material Symbols icon font
│   │   │   └── TypingIndicator.tsx Three-dot animated typing indicator
│   │   ├── layout/                App chrome — container components that read from UIStore
│   │   │   ├── index.ts           Barrel
│   │   │   ├── LayoutShell.tsx    Root layout container — composes SideNavBar + TopNavBar +
│   │   │   │                      main slot + BottomNavBar; applies sidebar offset transition
│   │   │   ├── TopNavBar.tsx      Top application bar — branding and top-level actions
│   │   │   ├── SideNavBar.tsx     Collapsible side navigation; receives collapsed +
│   │   │   │                      onToggleCollapse + activePath as props
│   │   │   └── BottomNavBar.tsx   Mobile bottom navigation bar — shown below md breakpoint
│   │   ├── ChatSession/           Top-level chat container — owns useSession + useChat;
│   │   │                          renders message list, fixed ChatInput footer, error alert,
│   │   │                          and post-completion CTA; auto-scrolls; fires initialMessage
│   │   ├── ChatInput/             Textarea + send button; fires onSend(trimmedMessage)
│   │   ├── ChatMessage/           Renders user / assistant message bubble; embeds result cards
│   │   ├── ModuleProgress/        Sticky step-progress bar (M1→M4); ModuleStep is internal
│   │   ├── BorrowingCapacityCard/ Displays BorrowingCapacityResult; disclaimer always rendered
│   │   └── BudgetGapCard/         Displays BudgetGapResult; returns null when has_gap is false
│   │
│   ├── stories/                   Ladle stories — mirrors component structure
│   │   ├── shared/                Stories for src/components/shared/* (one file per component)
│   │   ├── BorrowingCapacityCard.stories.tsx
│   │   ├── BudgetGapCard.stories.tsx
│   │   ├── ChatInput.stories.tsx
│   │   ├── ChatMessage.stories.tsx
│   │   └── ModuleProgress.stories.tsx
│   │
│   └── types/                     All type files end with .d.ts — mirrors backend models/ layout
│       ├── index.d.ts             Barrel — re-exports public surface of all type files
│       ├── conversation.d.ts      Domain enums (MODULE_ID, SESSION_STATUS, SUBMODEL_KEY, MESSAGE_ROLE),
│       │                          M1–M4 sub-model interfaces, CollectedData, ConversationStateDTO, UIMessage
│       ├── financial.d.ts         BorrowingCapacityResult, BudgetGapResult
│       │                          (mirrors backend models/financial.py — fields in snake_case because
│       │                          backend uses @dataclass, not PropertyAIBaseModel)
│       ├── user_needs.d.ts        UserNeeds interface (mirrors backend models/user_needs.py)
│       ├── routing.d.ts           USER_INTENT, EXECUTION_MODE, TRIGGER_SOURCE as const objects,
│       │                          derived union types, RoutingPayload interface
│       ├── ui.d.ts                ComponentSize, ComponentVariant, ComponentColor
│       │                          (derived from constants/ui.ts via typeof)
│       ├── api.d.ts               HTTP contract: APIResponse<TData>, ChatResponse, SummaryResponse,
│       │                          ErrorDetail, ErrorResponse, SuccessResponse
│       ├── global.d.ts            Ambient global type declarations
│       └── index.d.ts             Barrel — re-exports public surface of all type files
```

```
backend/
├── main.py                        FastAPI app factory — CORS middleware, router mount, /health
├── config.py                      pydantic-settings Settings class — single source of env vars
├── exceptions.py                  Typed exception hierarchy (PropertyAIException, LLMServiceError, …)
├── error_handlers.py              structlog configuration + FastAPI exception handler registration
│                                  (PropertyAIException → error envelope, RequestValidationError → 422)
├── scripts.py                     [project.scripts] entry points — test, lint, format_code,
│                                  typecheck, dev (thin wrappers around pytest/ruff/mypy/uvicorn)
├── pyproject.toml                 Canonical dependency + tool config (ruff, mypy, pytest)
├── requirements.txt               pip mirror of pyproject.toml — keep in sync manually
│
├── models/
│   ├── base.py                    PropertyAIBaseModel — shared Pydantic base with camelCase
│   │                              alias_generator; all public DTOs inherit from this class
│   ├── conversation_state.py      Enums (EModule, EStatus, ESubmodel, ESubmodelLabel),
│   │                              M1–M4 sub-models, CollectedData, CompletionStatus,
│   │                              ConversationStateDTO — the core conversation domain
│   ├── chat.py                    Chat API contract: ChatRequest, ChatResponse, RoutingPayload
│   │                              (v1.1: RoutingPayload now embeds UserNeeds, execution_mode,
│   │                              agents_hint, trigger_source, triggered_at)
│   ├── summary.py                 Summary API contract: SummaryRequest, SummaryResponse
│   ├── financial.py               Internal frozen dataclasses: BorrowingCapacityResult,
│   │                              BudgetGapResult, and suggested-action string constants
│   └── user_needs.py              Part 1 → Part 2 output contract: UserNeeds
│                                  (session_id, generated_at, schema_version, collected, initial_intent)
│
├── conversation/
│   ├── state_machine.py           Module progression — merges extracted fields, advances module,
│                                  recalculates completion, owns null-safety invariant
│   └── intent_router.py           Classifies each user message into a routing intent
│                                  (recommend_suburbs / list_properties / property_detail / open_ended_query)
│
├── prompts/
│   ├── system_prompt_builder.py   SOLE public interface — four build_* functions that assemble
│   │                              prompt strings; no prompt literals outside this package
│   └── sections/                  Internal sub-package (do not import outside prompts/)
│       ├── role.py                ROLE_DEFINITION — static assistant role block
│       ├── guardrails.py          GUARDRAIL_RULES — six compliance guardrail rules
│       ├── context.py             OWNER_OCCUPIER_CONTEXT, INVESTMENT_CONTEXT — M1 intent blocks
│       ├── instructions.py        EXTRACTION_INSTRUCTION, QUESTION_TASK_INSTRUCTION
│       ├── state.py               build_state_section, build_completed_list,
│       │                          build_collected_summary, build_missing_fields
│       └── financial.py           build_borrowing_capacity_section
│
├── domain/
│   ├── llm_client.py              OpenRouter async wrapper — implements ILLMClient Protocol,
│   │                              chat_with_tools_async (tool-calling) and complete_async (plain)
│   ├── borrowing_capacity.py      S-G: estimates borrowing capacity from salary data (28% DTI,
│   │                              ~25yr loan); returns BorrowingCapacityResult with disclaimer
│   ├── budget_gap_detector.py     S-H: compares budget_max against Domain API median price;
│   │                              returns BudgetGapResult and injects warning into system prompt
│   └── user_needs_builder.py      PRD §12: assembles UserNeeds snapshot for Part 1 → Part 2 handoff
│
├── tools/
│   └── extraction_schema.py       OpenAI-format tool definition that instructs the LLM to
│                                  return structured CollectedData fields
│
├── routers/
│   └── chat.py                    FastAPI route handlers — POST /chat and POST /chat/summary
│
└── tests/
    ├── conftest.py                 Shared fixtures: client_async (AsyncClient), sample_state
    ├── test_extraction_schema.py   S-A unit tests
    ├── test_state_machine.py       S-B unit tests
    ├── test_system_prompt.py       S-C unit tests
    ├── test_chat_endpoint.py       S-D integration tests
    ├── test_intent_router.py       S-E unit tests
    ├── test_summary.py             S-F integration tests
    ├── test_borrowing_capacity.py  S-G unit tests
    └── test_budget_gap_detector.py S-H unit tests
```

---

## Architecture Overview

PropertyAI guides users through four sequential conversation modules (M1→M4), collecting structured property requirements, then returns a formatted summary via `POST /chat/summary`.

### Request Flow

```
POST /api/v1/chat
    │
    ├── routers/chat.py
    │       1. Append user message to conversationHistory
    │       ── Round 1: Extraction ──────────────────────────────────────
    │       2. build_extraction_prompt(state)  →  prompts/system_prompt_builder.py
    │       3. chat_with_tools_async()         →  domain/llm_client.py  → extracted dict
    │       4. Merge extracted fields, advance module  →  conversation/state_machine.py
    │       ── Round 2: Question Generation ──────────────────────────────
    │       5. build_question_prompt(updated_state)  →  prompts/system_prompt_builder.py
    │       6. complete_async()               →  domain/llm_client.py  → reply str
    │       7. Append reply to conversationHistory
    │       8. Classify intent  →  conversation/intent_router.py
    │       9. Return ChatResponse (reply + extracted + updated_state + routing)
    │
POST /api/v1/chat/summary
    │
    └── routers/chat.py
            Validates non-empty data, builds summary prompt, calls LLM plain completion
```

### Module Progression

```
EModule:  M1_PROPERTY_NEEDS → M2_LIFESTYLE → M3_SUBURB_PREFERENCE → M4_BUDGET → COMPLETE
EStatus:  IN_PROGRESS ────────────────────────────────────────────► REQUIREMENTS_COMPLETE
```

| Module | Required fields to advance                                                               |
| ------ | ---------------------------------------------------------------------------------------- |
| M1     | `property_type`, `min_bedrooms`, `intended_use`                                          |
| M2     | `household_size`, `has_children` (+ `target_tenant` when `intended_use == "investment"`) |
| M3     | `commute_destination`, `commute_max_mins`                                                |
| M4     | `budget_max`                                                                             |

---

## Key Invariants

These are non-obvious constraints that must never be violated, regardless of context:

**Backend**

1. **Null-safety** — a non-`None` value in `CollectedData` is never overwritten by `None`. Owned by `state_machine.py`. See [backend-patterns.md](.claude/rules/backend/backend-patterns.md).

2. **Prompt locality** — all LLM prompt strings live exclusively in `prompts/system_prompt_builder.py`. No prompt literals anywhere else. See [backend-patterns.md](.claude/rules/backend/backend-patterns.md).

3. **Error envelope** — all 4xx/5xx responses use `{"error": {"code": "...", "message": "...", "details": {}}}`. Raw FastAPI `{"detail": "..."}` is forbidden for business errors. See [backend-patterns.md](.claude/rules/backend/backend-patterns.md).

4. **Async naming** — every `async def` function carries the `_async` suffix. No exceptions, including FastAPI route handlers and pytest fixtures. See [coding-standards.md](.claude/rules/backend/coding-standards.md).

5. **No `os.getenv` in business logic** — all config is read from the `Settings` pydantic-settings class in `config.py`. See [backend-patterns.md](.claude/rules/backend/backend-patterns.md).

6. **LLM calls are always mocked in tests** — no live API calls in the test suite. See [testing.md](.claude/rules/backend/testing.md).

**Frontend**

7. **Complete state replacement** — `setUpdatedState` in `conversationStore` must do a full replacement, never `Object.assign` or spread merge. See [coding-standards.md](.claude/rules/frontend/coding-standards.md).

8. **No magic domain strings** — any string used as a domain identifier in more than one file must be defined as an `as const` object entry. See [coding-standards.md](.claude/rules/frontend/coding-standards.md).

9. **No direct axios/fetch in components or hooks** — all HTTP calls go through `services/`. `lib/request.ts` is internal to the service layer; do not import it outside `services/`. See [coding-standards.md](.claude/rules/frontend/coding-standards.md).

10. **Theme tokens first** — colors, font sizes, and spacing must come from `globals.css` `@theme`; Tailwind built-in design values are forbidden. See [coding-standards.md](.claude/rules/frontend/coding-standards.md).

11. **UI/Container separation** — UI components must not read from stores or call hooks directly. See [coding-standards.md](.claude/rules/frontend/coding-standards.md).

12. **API calls mocked in tests** — no live network requests; use MSW handlers. See [testing.md](.claude/rules/frontend/testing.md).

13. **Type files end in `.d.ts`** — all files under `src/types/` use the `.d.ts` extension. Do not create `.ts` files there.

14. **`CollectedData` keys driven by `SUBMODEL_KEY`** — use `SUBMODEL_KEY.M1` / `M2` / `M3` / `M4` as computed keys; do not write `'m1'` / `'m2'` literals outside `conversation.d.ts`.

15. **Financial types stay snake_case** — `BorrowingCapacityResult` and `BudgetGapResult` use snake_case field names because the backend serialises them from `@dataclass` (not `PropertyAIBaseModel`), bypassing the camelCase `alias_generator`.

---

## Naming Quick Reference

| Construct            | Pattern            | Example                         |
| -------------------- | ------------------ | ------------------------------- |
| Async function       | `snake_case_async` | `call_llm_async`, `chat_async`  |
| Enum class           | `E` + PascalCase   | `EModule`, `EUserIntent`        |
| Protocol (interface) | `I` + PascalCase   | `ILLMClient`, `IChatService`    |
| TypeVar / TypeAlias  | `T` + PascalCase   | `TState`, `TResponse`           |
| Private attribute    | `_` + snake_case   | `_session_id`, `_build_context` |
| Constant             | SCREAMING_SNAKE    | `MAX_TOKENS`, `DEFAULT_MODEL`   |

Full conventions: [coding-standards.md](.claude/rules/backend/coding-standards.md)
