# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Rules Index

Detailed standards live in `.claude/rules/` — read the relevant file before touching that area:

| File | When to read |
|---|---|
| [coding-standards.md](.claude/rules/coding-standards.md) | Any time you write or review code — naming, types, docstrings, SOLID/DRY/KISS |
| [backend-patterns.md](.claude/rules/backend-patterns.md) | Config, logging, exceptions, API error envelope, prompt placement, null-safety |
| [testing.md](.claude/rules/testing.md) | Writing or modifying tests — coverage thresholds, mock rules, test naming |
| [git-workflow.md](.claude/rules/git-workflow.md) | Commits, branches, PRs, pre-commit hooks |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| API framework | FastAPI |
| Data validation | Pydantic v2 |
| LLM gateway | OpenRouter API |
| Session store | Redis |
| Database | PostgreSQL (JSONB for semi-structured fields) |
| Dependency manager | uv + `pyproject.toml` |
| Formatter + Linter | Ruff (line-length 100) |
| Type checker | mypy `--strict` |
| Test framework | pytest (asyncio_mode = auto) |
| Logging | structlog (JSON output) |

---

## Development Commands

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
backend/
├── main.py                        FastAPI app factory — CORS middleware, router mount, /health
├── pyproject.toml                 Canonical dependency + tool config (ruff, mypy, pytest)
├── requirements.txt               pip mirror of pyproject.toml — keep in sync manually
│
├── models/
│   └── schemas.py                 All Pydantic DTOs and domain models (ConversationStateDTO,
│                                  CollectedData, ChatRequest, ChatResponse, SummaryResponse)
│
├── conversation/
│   ├── state_machine.py           Core orchestrator — loads Redis state, dispatches to active
│                                  module, calls LLM, merges extracted fields, advances module
│   └── intent_router.py           Classifies each user message into a routing intent
│                                  (recommend_suburbs / list_properties / property_detail / open_ended_query)
│
├── prompts/
│   └── system_prompt_builder.py   SOLE source of all LLM prompt strings — no prompt literals
│                                  anywhere else in the codebase
│
├── services/
│   └── llm_client.py              OpenRouter async wrapper — implements ILLMClient Protocol,
│                                  handles tool-calling and retries
│
├── tools/
│   └── extraction_schema.py       OpenAI-format tool definition that instructs the LLM to
│                                  return structured CollectedData fields
│
├── routers/
│   └── chat.py                    FastAPI route handlers — POST /chat (chat_async),
│                                  POST /chat/summary (chat_summary_async)
│
└── tests/
    ├── conftest.py                 Shared fixtures: client_async (AsyncClient), sample_state
    ├── test_state_machine.py       Unit tests for conversation/state_machine.py        [S-B]
    ├── test_intent_router.py       Unit tests for conversation/intent_router.py        [S-E]
    ├── test_system_prompt.py       Unit tests for prompts/system_prompt_builder.py     [S-C]
    ├── test_extraction_schema.py   Unit tests for tools/extraction_schema.py           [S-C]
    ├── test_chat_endpoint.py       Integration tests for POST /chat                    [S-D]
    └── test_summary.py             Integration tests for POST /chat/summary            [S-F]
```

---

## Architecture Overview

PropertyAI guides users through four sequential conversation modules, collecting structured property requirements, then returns a formatted summary via `POST /chat/summary`.

### Request Flow

```
POST /api/v1/chat
    │
    ├── routers/chat.py              Validates request, delegates to state machine
    │
    ├── conversation/intent_router.py
    │       Classifies intent — recommend_suburbs / list_properties / property_detail / open_ended_query
    │
    ├── conversation/state_machine.py
    │       1. Loads ConversationState from Redis (keyed by session_id)
    │       2. Builds system prompt via system_prompt_builder.py
    │       3. Calls LLM via llm_client.py (with extraction_schema.py tool)
    │       4. Merges extracted fields into CollectedData (null-safety invariant)
    │       5. Advances module if all required fields are non-None
    │       6. Persists updated state to Redis
    │       7. Returns assistant reply
    │
    ├── prompts/system_prompt_builder.py
    │       Builds module-specific system prompt from current state
    │
    ├── services/llm_client.py
    │       Async OpenRouter call with tool-calling support
    │
    └── tools/extraction_schema.py
            Tool definition that forces structured field extraction
```

### Session State (Redis)

State is serialised as JSON and stored at key `session:{session_id}`.

```
ConversationState
├── session_id: str
├── current_module: EModule          — active module driving the conversation
├── status: EStatus                  — IN_PROGRESS | REQUIREMENTS_COMPLETE
├── messages: list[Message]          — full chat history (role + content)
└── collected_data: CollectedData    — accumulated field values across all modules
```

`CollectedData` is the single accumulator for all extracted fields. Fields are owned by a specific module but stored flat so the summary endpoint can read everything in one pass.

### Module Progression

```
EModule:  M1_PROPERTY_NEEDS → M2_LIFESTYLE → M3_SUBURB_PREFERENCE → M4_BUDGET → COMPLETE
EStatus:  IN_PROGRESS ──────────────────────────────────────────────────────► REQUIREMENTS_COMPLETE
```

| Module | Collects |
|---|---|
| M1_PROPERTY_NEEDS | Property type, bedrooms, bathrooms, parking, key features |
| M2_LIFESTYLE | Lifestyle priorities, commute destination, pet/family requirements |
| M3_SUBURB_PREFERENCE | Preferred suburbs, max distance, school zone requirements |
| M4_BUDGET | Budget min/max, deposit readiness |

The state machine advances only when **all required fields for the current module are non-`None`**. Optional fields do not block advancement.

### Domain Enums

```python
class EModule(str, Enum):
    M1_PROPERTY_NEEDS    = "M1_PROPERTY_NEEDS"
    M2_LIFESTYLE         = "M2_LIFESTYLE"
    M3_SUBURB_PREFERENCE = "M3_SUBURB_PREFERENCE"
    M4_BUDGET            = "M4_BUDGET"
    COMPLETE             = "COMPLETE"

class EStatus(str, Enum):
    IN_PROGRESS            = "IN_PROGRESS"
    REQUIREMENTS_COMPLETE  = "REQUIREMENTS_COMPLETE"

class EUserIntent(str, Enum):
    RECOMMEND_SUBURBS  = "recommend_suburbs"   # user asking for suburb recommendations
    LIST_PROPERTIES    = "list_properties"     # user asking to list matching properties
    PROPERTY_DETAIL    = "property_detail"     # user asking about a specific property
    OPEN_ENDED_QUERY   = "open_ended_query"    # general query after requirements are complete
```

---

## Key Invariants

These are non-obvious constraints that must never be violated, regardless of context:

1. **Null-safety** — a non-`None` value in `CollectedData` is never overwritten by `None`. Owned by `state_machine.py`. See `backend-patterns.md`.

2. **Prompt locality** — all LLM prompt strings live exclusively in `prompts/system_prompt_builder.py`. No prompt literals anywhere else. See `backend-patterns.md`.

3. **Error envelope** — all 4xx/5xx responses use `{"error": {"code": "...", "message": "...", "details": {}}}`. Raw FastAPI `{"detail": "..."}` is forbidden for business errors. See `backend-patterns.md`.

4. **Async naming** — every `async def` function carries the `_async` suffix. No exceptions, including FastAPI route handlers and pytest fixtures. See `coding-standards.md`.

5. **No `os.getenv` in business logic** — all config is read from the `Settings` pydantic-settings class in `config.py`. See `backend-patterns.md`.

6. **LLM calls are always mocked in tests** — no live API calls in the test suite. See `testing.md`.

---

## Naming Quick Reference

| Construct | Pattern | Example |
|---|---|---|
| Async function | `snake_case_async` | `call_llm_async`, `chat_async` |
| Enum class | `E` + PascalCase | `EModule`, `EUserIntent` |
| Protocol (interface) | `I` + PascalCase | `ILLMClient`, `IChatService` |
| TypeVar / TypeAlias | `T` + PascalCase | `TState`, `TResponse` |
| Private attribute | `_` + snake_case | `_session_id`, `_build_context` |
| Constant | SCREAMING_SNAKE | `MAX_TOKENS`, `DEFAULT_MODEL` |

Full conventions: [coding-standards.md](.claude/rules/coding-standards.md)

---

## Implementation Status

| File | Story | Status |
|---|---|---|
| `main.py` | — | Done (skeleton) |
| `routers/chat.py` | S-D, S-F | Stub — returns 501 |
| `models/schemas.py` | S-B | Stub — placeholder DTO only |
| `conversation/state_machine.py` | S-B | Stub |
| `conversation/intent_router.py` | S-E | Stub |
| `prompts/system_prompt_builder.py` | S-C | Stub |
| `services/llm_client.py` | S-C | Stub |
| `tools/extraction_schema.py` | S-C | Stub |
| `tests/conftest.py` | — | Done (fixtures) |
| `tests/test_state_machine.py` | S-B | Placeholder only |
| `tests/test_intent_router.py` | S-E | Placeholder only |
| `tests/test_system_prompt.py` | S-C | Placeholder only |
| `tests/test_extraction_schema.py` | S-C | Placeholder only |
| `tests/test_chat_endpoint.py` | S-D | Placeholder only |
| `tests/test_summary.py` | S-F | Placeholder only |
