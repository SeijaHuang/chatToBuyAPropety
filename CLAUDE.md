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

## Docs Index

| File | Contents |
|---|---|
| [docs/part1-p0-implementation.md](docs/part1-p0-implementation.md) | Part 1 P0 story completion, E2E criteria, architectural decisions, test coverage |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| API framework | FastAPI |
| Data validation | Pydantic v2 |
| LLM gateway | OpenRouter API |
| Session store | Redis (P1 — not active in P0) |
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
├── config.py                      pydantic-settings Settings class — single source of env vars
├── exceptions.py                  Typed exception hierarchy (PropertyAIException, LLMServiceError, …)
├── pyproject.toml                 Canonical dependency + tool config (ruff, mypy, pytest)
├── requirements.txt               pip mirror of pyproject.toml — keep in sync manually
│
├── models/
│   ├── conversation_state.py      Enums (EModule, EStatus, ESubmodel, ESubmodelLabel),
│   │                              M1–M4 sub-models, CollectedData, CompletionStatus,
│   │                              ConversationStateDTO — the core conversation domain
│   ├── chat.py                    Chat API contract: ChatRequest, ChatResponse, RoutingPayload
│   └── summary.py                 Summary API contract: SummaryRequest, SummaryResponse
│
├── conversation/
│   ├── state_machine.py           Module progression — merges extracted fields, advances module,
│                                  recalculates completion, owns null-safety invariant
│   └── intent_router.py           Classifies each user message into a routing intent
│                                  (recommend_suburbs / list_properties / property_detail / open_ended_query)
│
├── prompts/
│   └── system_prompt_builder.py   SOLE source of all LLM prompt strings — no prompt literals
│                                  anywhere else in the codebase
│
├── services/
│   └── llm_client.py              OpenRouter async wrapper — implements ILLMClient Protocol,
│                                  chat_with_tools_async (tool-calling) and complete_async (plain)
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
    └── test_summary.py             S-F integration tests
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
    │       3. chat_with_tools_async()         →  services/llm_client.py  → extracted dict
    │       4. Merge extracted fields, advance module  →  conversation/state_machine.py
    │       ── Round 2: Question Generation ──────────────────────────────
    │       5. build_question_prompt(updated_state)  →  prompts/system_prompt_builder.py
    │       6. complete_async()               →  services/llm_client.py  → reply str
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

| Module | Required fields to advance |
|---|---|
| M1 | `property_type`, `min_bedrooms`, `intended_use` |
| M2 | `household_size`, `has_children` (+ `target_tenant` when `intended_use == "investment"`) |
| M3 | `commute_destination`, `commute_max_mins` |
| M4 | `budget_max` |

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
