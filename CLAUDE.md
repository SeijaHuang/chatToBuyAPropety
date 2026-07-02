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
| [docs/backend-implementation.md](docs/backend-implementation.md)               | **Backend feature index** — full source map, request/data flow, session & identity persistence model, exception hierarchy, coverage targets, PRD deviations. Read this before adding or changing any backend feature |
| [docs/frontend-implementation.md](docs/frontend-implementation.md)             | **Frontend feature index** — full source map, data flow, state persistence, component hierarchy, coverage targets. Read this before adding or changing any frontend feature |
| [PRD/PropertyAI_PRD_v1_1.md](PRD/PropertyAI_PRD_v1_1.md)                      | Authoritative PRD v1.1 — P0 stories S-A→S-H, P1 stories §20–26, data models, error handling spec |

---

## Backend Tech Stack

| Layer              | Technology                                    |
| ------------------ | --------------------------------------------- |
| Language           | Python 3.12                                   |
| API framework      | FastAPI                                       |
| Data validation    | Pydantic v2                                   |
| LLM gateway        | OpenRouter API                                |
| Session store      | Redis — full conversation state, sliding 7-day TTL (active) |
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

**Frontend** — the full `frontend/src/` tree, one-line file responsibilities, data flow, and state persistence live exclusively in [docs/frontend-implementation.md](docs/frontend-implementation.md). Read it before adding code to an existing frontend file or deciding where new frontend code belongs; do not re-duplicate the tree here.

**Backend** — the full `backend/` tree, one-line file responsibilities, request/data flow, and the session & identity persistence model live exclusively in [docs/backend-implementation.md](docs/backend-implementation.md). Read it before adding code to an existing backend file or deciding where new backend code belongs; do not re-duplicate the tree here.

---

## Architecture Overview

PropertyAI guides users through four sequential conversation modules (M1→M4), collecting structured property requirements, then returns a formatted summary via `POST /chat/summary`.

### Request Flow

`POST /api/v1/chat` loads/creates session state from Redis (not from the request body), runs the two-round LLM architecture, persists back to Redis, and best-effort-upserts a history snapshot to Postgres. `GET /api/v1/chat/{session_id}` restores a session; `GET /api/v1/chats` lists a user's session history; `POST /api/v1/chat/summary` is unchanged (stateless). The full step-by-step processing order, endpoint list, and the Redis/Postgres/cookie persistence model live in [docs/backend-implementation.md](docs/backend-implementation.md) — do not re-duplicate the flow diagram here.

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
