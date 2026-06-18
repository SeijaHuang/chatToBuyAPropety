# PropertyAI

An AI-powered property-buying assistant that guides users through a structured conversation to collect their property requirements, then returns a structured summary for downstream property matching.

---

## Prerequisites

**Backend**
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (`pip install uv`)
- Docker + Docker Compose (for Postgres and Redis)

**Frontend**
- Node.js 20+
- [pnpm](https://pnpm.io) (`npm install -g pnpm`)

---

## Quick Start

### Backend

```bash
# 1. Start infrastructure
docker-compose up -d redis postgres

# 2. Install dependencies
cd backend
uv sync

# 3. Copy and populate environment variables
cp .env.example .env   # then fill in OPENROUTER_API_KEY

# 4. Run the dev server
uv run uvicorn main:app --reload --port 8000
```

API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend

# 1. Install dependencies
pnpm install

# 2. Copy and populate environment variables
cp .env.example .env.local   # set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# 3. Run the dev server
pnpm dev
```

App is available at `http://localhost:3000`.

---

## Environment Variables

### Backend

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | API key for OpenRouter LLM gateway |
| `MODEL_STRONG` | No | Model for complex reasoning (default: `anthropic/claude-sonnet-4-5`) |
| `MODEL_FAST` | No | Model for intent classification (default: `anthropic/claude-haiku-4-5`) |
| `REDIS_URL` | No | Redis connection string (default: `redis://localhost:6379`) |
| `DATABASE_URL` | No | Postgres connection string (default: `postgresql://user:password@localhost:5432/propertyai`) |

### Frontend

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Backend base URL (e.g. `http://localhost:8000`) |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/v1/chat` | Send a user message; returns assistant reply + updated state |
| `POST` | `/api/v1/chat/summary` | Return structured property requirements summary |

---

## Running Tests

### Backend

```bash
cd backend

# Full suite with coverage
uv run pytest

# Single file
uv run pytest tests/test_state_machine.py

# Single test
uv run pytest tests/test_state_machine.py::test_advance_on_required_fields_collected
```

### Frontend

```bash
cd frontend

pnpm test        # vitest watch mode
pnpm test:run    # single run
```

---

## Linting & Type Checking

### Backend

```bash
cd backend

uv run ruff check .          # lint
uv run ruff format --check . # format check
uv run ruff format .         # auto-fix formatting
uv run mypy --strict .       # type check
```

### Frontend

```bash
cd frontend

pnpm lint        # ESLint
pnpm type-check  # tsc --noEmit
```

---

## Project Structure

```
backend/
├── main.py                          # FastAPI app + middleware setup
├── config.py                        # pydantic-settings config (reads .env)
├── models/                          # Pydantic DTOs and domain enums
├── conversation/                    # State machine + intent router
│   ├── state_machine.py
│   └── intent_router.py
├── prompts/system_prompt_builder.py # All LLM system prompts
├── domain/                          # LLM client, borrowing capacity, budget gap, user needs
├── routers/chat.py                  # /chat and /chat/summary endpoints
└── tests/

frontend/
├── src/
│   ├── app/                         # Next.js App Router — root layout + (main) route group
│   │   └── (main)/                  #   layout.tsx (LayoutShell), page.tsx (home), chat/[sessionId]/
│   ├── constants/                   # as-const value objects (MODULE_ID, USER_INTENT, STORAGE_KEY…)
│   ├── lib/                         # request.ts (axios), utils.ts (cn, createInitialState), tv.ts
│   ├── services/                    # Domain API calls — postChat, postChatSummary
│   ├── stores/                      # Zustand — conversationStore, uiStore
│   ├── hooks/                       # useChat, useSession
│   ├── components/
│   │   ├── shared/                  # UI atoms — Button, Chip, AIBadge, Skeleton, TypingIndicator
│   │   ├── layout/                  # App chrome — LayoutShell, TopNavBar, SideNavBar, BottomNavBar
│   │   └── (domain)/                # ChatSession, ChatInput, ChatMessage, ModuleProgress,
│   │                                #   BorrowingCapacityCard, BudgetGapCard
│   ├── styles/                      # Tailwind CSS v4 @theme design tokens
│   └── types/                       # TypeScript .d.ts declarations (conversation, api, financial…)
└── src/__tests__/                   # Vitest tests mirroring src/ structure
```

See `CLAUDE.md` for full coding standards, architecture details, and invariants.  
See `docs/frontend-implementation.md` for the complete frontend source map and data-flow diagram.
