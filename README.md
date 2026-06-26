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

### 1. Start infrastructure

```bash
# Start Postgres and Redis (from repo root)
docker-compose up -d redis postgres
```

### 2. Backend

```bash
cd backend

# Install dependencies
uv sync

# Copy and populate environment variables
cp .env.example .env   # fill in OPENROUTER_API_KEY at minimum

# Run database migrations
uv run alembic upgrade head

# Start the dev server
uv run uvicorn main:app --reload --port 8000
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 3. Frontend

```bash
cd frontend

# Install dependencies
pnpm install

# Copy and populate environment variables
cp .env.example .env.local   # set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# Start the dev server
pnpm dev
```

App available at `http://localhost:3000`.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Yes | — | API key for OpenRouter LLM gateway |
| `MODEL_STRONG` | No | `anthropic/claude-sonnet-4-5` | Model for complex reasoning |
| `MODEL_FAST` | No | `anthropic/claude-haiku-4-5` | Model for intent classification |
| `LLM_BASE_URL` | No | `https://openrouter.ai/api/v1` | LLM API base URL (leave empty to use OpenAI SDK default) |
| `DATABASE_URL` | No | `postgresql://user:password@localhost:5432/propertyai` | Postgres connection string (auto-converted to `asyncpg` driver) |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis connection string |
| `REDIS_SESSION_TTL` | No | `604800` | Session TTL in seconds (default: 7 days) |
| `DOMAIN_API_KEY` | No | — | Domain.com.au API key for median price lookups |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Backend base URL (e.g. `http://localhost:8000`) |

---

## Database Migrations (Alembic)

```bash
cd backend

# Apply all pending migrations
uv run alembic upgrade head

# Roll back one migration
uv run alembic downgrade -1

# Generate a new migration after model changes
uv run alembic revision --autogenerate -m "describe your change"
```

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
├── main.py                          # FastAPI app + CORS middleware
├── config.py                        # pydantic-settings config (reads .env)
├── exceptions.py                    # Typed exception hierarchy
├── error_handlers.py                # Global exception → HTTP error envelope
├── alembic.ini                      # Alembic migration config
│
├── models/                          # Pydantic DTOs and domain enums
│   ├── base.py                      #   PropertyAIBaseModel (camelCase aliases)
│   ├── conversation_state.py        #   EModule, EStatus, CollectedData, ConversationStateDTO
│   ├── chat.py                      #   ChatRequest, ChatResponse, RoutingPayload
│   ├── summary.py                   #   SummaryRequest, SummaryResponse
│   ├── financial.py                 #   BorrowingCapacityResult, BudgetGapResult (dataclasses)
│   └── user_needs.py                #   UserNeeds (Part 1 → Part 2 handoff contract)
│
├── conversation/
│   ├── state_machine.py             # Module progression, field merging, completion logic
│   └── intent_router.py            # Classifies user message into routing intent
│
├── prompts/
│   └── system_prompt_builder.py    # Sole public interface for all LLM prompt assembly
│
├── domain/
│   ├── llm_client.py               # OpenRouter async wrapper (ILLMClient Protocol)
│   ├── borrowing_capacity.py       # Estimates borrowing capacity from salary
│   ├── budget_gap_detector.py      # Compares budget vs Domain API median price
│   └── user_needs_builder.py       # Assembles UserNeeds snapshot
│
├── db/
│   ├── connection.py               # SQLAlchemy async engine + session factory
│   ├── models/
│   │   └── chat.py                 #   ORM model for chat sessions (JSONB fields)
│   ├── repositories/
│   │   └── chat.py                 #   ChatRepository — async CRUD via SQLAlchemy
│   └── alembic/                    # Migration scripts
│       └── versions/
│           └── 993128e7e195_create_chats.py
│
├── redis_store/
│   ├── client.py                   # Redis async client factory
│   ├── session_store.py            # Session persistence (conversation state)
│   └── price_cache.py              # Domain API median price cache
│
├── routers/
│   └── chat.py                     # /chat and /chat/summary route handlers
│
└── tests/
    ├── conftest.py
    ├── test_chat_repository.py
    ├── test_extraction_schema.py
    ├── test_state_machine.py
    ├── test_system_prompt.py
    ├── test_chat_endpoint.py
    ├── test_intent_router.py
    ├── test_summary.py
    ├── test_borrowing_capacity.py
    └── test_budget_gap_detector.py

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
