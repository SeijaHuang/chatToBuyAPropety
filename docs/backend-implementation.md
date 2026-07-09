# Backend Implementation

| Field | Value |
|---|---|
| Language | Python 3.12 |
| API framework | FastAPI |
| Data validation | Pydantic v2 |
| LLM gateway | OpenRouter API (via `openai` SDK) |
| Session store | **Redis** — full `ConversationStateDTO`, sliding 7-day TTL (now active, not P1) |
| History store | **PostgreSQL** — `users` + `chats` tables via SQLAlchemy 2.0 async + `asyncpg`, migrated with Alembic |
| Identity | Anonymous, cookie-based (`propertyai_anon_id`, HttpOnly) — no login yet |
| Dependency manager | uv + `pyproject.toml` |
| Formatter + Linter | Ruff (line-length 100) |
| Type checker | mypy `--strict` |
| Test framework | pytest (`asyncio_mode = auto`) |
| Logging | structlog (JSON-compatible console output) |

---

## Architecture Overview

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/chat` | Process one conversation turn — create or continue a session |
| `GET` | `/api/v1/chat/{session_id}` | Restore session state (page reload / revisit) — Redis hit, or Postgres fallback with an LLM-generated welcome-back message |
| `GET` | `/api/v1/chats` | List the current anonymous user's chat sessions (sidebar history) |
| `POST` | `/api/v1/chat/summary` | Generate a natural-language requirements summary |
| `GET` | `/health` | Liveness — checks both Redis and Postgres connectivity |

Unlike the original P0 design, **the frontend no longer sends `ConversationStateDTO` in the request body.** `ChatRequest` carries only `session_id | null` and `message`; all state lives server-side in Redis and is loaded/created per request. See "Session & Identity Persistence Model" below.

### Two-round LLM architecture (unchanged from P0)

Each `POST /chat` call issues two LLM calls:

1. **Round 1 — Extraction**: minimal system prompt (`build_extraction_prompt`) + `extract_requirements` tool. Produces a structured `dict` of extracted fields. `state_machine.merge_extracted_fields()` merges them into state and advances the module.
2. **Round 2 — Question generation**: full system prompt (`build_question_prompt`) including role definition, current state, optional M1→M2 context, borrowing capacity, budget gap warning, and guardrail rules. Produces the assistant reply text.

This separation keeps Round 1 free from conversational noise (improving extraction precision) and Round 2 free from tool-calling constraints (improving reply quality). The cost is one extra LLM call per turn.

### `POST /chat` processing order (as-built, `routers/chat.py::chat_async`)

1. `resolved_anon_id` is injected by the `resolve_anon_id_async` Cookie dependency — always a valid DB-backed string (auto-creates a `users` row on first visit).
2. Load state from Redis by `session_id`; auto-create a fresh `ConversationStateDTO` if `session_id` is `None` or absent from Redis.
3. Append the user message to `conversation_history`.
4. Round 1 — Extraction (see above); malformed tool-call JSON is caught and logged, extraction degrades to `{}` rather than failing the turn.
5. Merge extracted fields into state (advances module, recalculates `completion_status`).
6. Recompute `borrowing_capacity` (if `pre_tax_salary` present) and `budget_gap` (if `budget_max` + a suburb are present).
7. Round 2 — Question generation.
8. Append the assistant reply to `conversation_history`.
9. Persist the updated full state back to Redis (resets the 7-day sliding TTL).
10. Classify intent (`intent_router.classify_intent`) for downstream Part-2 routing.
11. Schedule a Postgres upsert via `BackgroundTasks` — only when this is a new session or any module newly completed this turn (never on every turn).
12. Set the `propertyai_anon_id` HttpOnly cookie and return `ChatResponse` (reply, extracted fields, `session_id`, a `ConversationSnapshotDTO`, optional `routing`).

---

## Session & Identity Persistence Model

Two separate stores serve two separate purposes — do not conflate them:

| Store | Holds | Written | Source of truth for |
|---|---|---|---|
| **Redis** (`redis_store/session_store.py`) | Full `ConversationStateDTO`, including `conversation_history` | Every turn, synchronously, before the response is sent | The live conversation — what `GET /chat/{session_id}` restores |
| **PostgreSQL `chats` table** (`db/repositories/chat.py`) | A lightweight progressive snapshot (`status`, `initial_intent`, `collected_data` JSONB, `final_needs` JSONB, `borrowing_capacity` JSONB, timestamps) | Best-effort, via `BackgroundTasks`, only on session creation or module completion | The sidebar history list (`GET /chats`) — never read back into a live turn |

Key: `session:{session_id}` → JSON (`ConversationStateDTO.model_dump_json`). TTL is **sliding** — every `save_session_async` call resets it to `redis_session_ttl` (default 604800s / 7 days).

Upserts use `INSERT ... ON CONFLICT (session_id) DO UPDATE`, with `COALESCE` guards so `initial_intent` and `completed_at` are never overwritten back to `NULL` once set. `SqlAlchemyChatRepository.upsert_chat_snapshot_async` catches and logs all exceptions internally — a Postgres outage must never fail or block the chat turn, since the write happens after the HTTP response has already been prepared.

### Session restore — Redis miss falls back to Postgres

`GET /chat/{session_id}` (`routers/chat.py::get_session_async`) no longer 404s the moment the Redis key has expired. On a Redis hit it returns immediately (`resume_message: null`, full `conversation_history`). On a Redis miss it queries `chat_repo.get_chat_snapshot_async(session_id)` for the lightweight Postgres snapshot; a Postgres miss too is still a genuine `SessionNotFoundError` (404). On a Postgres hit:

1. `collected_data` / `borrowing_capacity` are deserialised from JSONB back into domain objects.
2. `conversation/state_machine.py::recalculate_completion()` and `get_current_module()` re-derive `completion_status` / `current_module` from `collected_data` — neither is persisted to Postgres, so both must be recomputed rather than trusted from storage.
3. `prompts/system_prompt_builder.py::build_session_restore_prompt()` (distinct from `build_question_prompt` / `build_summary_prompt`) builds a prompt instructing the LLM to write a short, jargon-free welcome-back message; `llm_client.complete_async()` generates it.
4. The generated message is appended to `conversation_history` as the first assistant turn, then `save_session_async()` re-seeds Redis so the next request is a cache hit again. A re-seed failure is logged and swallowed — the response has already been prepared, and the Postgres row is untouched either way.
5. The endpoint returns `ChatSessionRestoreResponse { resume_message, state, conversation_history }` — `resume_message` is `null` on a Redis hit and the generated string on a Postgres restore; the frontend distinguishes the two cases by that field alone, since the rest of the response shape is identical.

If the LLM call itself fails during a Postgres restore, `LLMServiceError` (503) is raised and Redis is deliberately **not** re-seeded, so the next request retries the same restore path rather than caching a half-finished state.

### Anonymous identity

A single `users` table (`db/orm/user.py`) covers both anonymous and future registered users:

- `anon_id` (unique UUID) — always set; the value round-tripped via the `propertyai_anon_id` cookie.
- `email` (nullable, unique) — `NULL` for anonymous users; populated on registration (P1-B), on the **same row** — no migration of `chats` rows required when a user logs in.

Two FastAPI dependencies in `routers/deps.py` govern identity resolution:

| Dependency | Behaviour | Used by |
|---|---|---|
| `resolve_anon_id_async` | Missing/malformed cookie → silently creates a new `users` row and a fresh `anon_id`. Never fails. | `POST /chat` |
| `require_anon_id_cookie_async` | Missing/malformed cookie → `BadRequestError` (400). Never auto-creates. | `GET /chats` |

The cookie is set in the `POST /chat` response only (`HttpOnly`, `SameSite=Strict`, `Secure` per `settings.cookie_secure`, `path=/api/v1`, `Max-Age` per `settings.cookie_max_age` — default 1 year). `chats.anon_id` is a denormalised copy of `users.anon_id` with no foreign key — `chats.user_id` is reserved, unwritten until P1-B login lands.

### Price cache (unrelated to session state, also Redis-backed)

`redis_store/price_cache.py` caches Domain API median-price lookups used by `budget_gap_detector.py`, keyed `price:{suburb}:{property_type}:{min_bedrooms}`, fixed (non-sliding) 24-hour TTL. Cache misses and Redis errors both fall through to a live Domain API call — never raise.

---

## Source File Map

```
backend/
├── main.py                        FastAPI app factory — lifespan manages Redis + Postgres
│                                  connection lifecycle, CORS middleware, router mount,
│                                  /health (checks both Redis and Postgres)
├── config.py                      pydantic-settings Settings class — LLM, financial calc,
│                                  database_url (auto-upgrades postgresql:// → +asyncpg),
│                                  redis_url / redis_session_ttl, CORS origins, cookie settings
├── exceptions.py                  Typed exception hierarchy (PropertyAIException, LLMServiceError,
│                                  StateTransitionError, SummaryValidationError, BadRequestError,
│                                  RateLimitError, SessionNotFoundError)
├── error_handlers.py              structlog configuration + FastAPI exception handler registration
│                                  (PropertyAIException → error envelope, RequestValidationError → 422)
├── cli.py                          [project.scripts] entry points — test, lint, format_code,
│                                  typecheck, dev (docker-compose up → _migrate (Alembic, retries
│                                  while Postgres starts) → uvicorn)
├── pyproject.toml                 Canonical dependency + tool config (ruff, mypy, pytest)
├── requirements.txt               pip mirror of pyproject.toml — keep in sync manually
│
├── models/                        Organised by API-contract layer, not domain concept — see
│   │                              backend-patterns.md#models-package-layout for the full rule
│   ├── base.py                    PropertyAIBaseModel — shared Pydantic base with camelCase
│   │                              alias_generator; ErrorDetail, ErrorResponse, SuccessResponse[T]
│   ├── shared/                    Cross-endpoint models — enums.py (EModule, EStatus, ESubmodel,
│   │                              ESubmodelLabel, EUserIntent, EPropertyType, EIntendedUse,
│   │                              ETargetTenant, ECommuteMode, ELifestyleVibe), submodels.py
│   │                              (M1–M4 sub-models, CollectedData, CompletionStatus),
│   │                              conversation_state.py (ConversationStateDTO), financial.py
│   │                              (BorrowingCapacityResult, BudgetGapResult), user_needs.py
│   │                              (UserNeeds), routing.py (RoutingPayload, EExecutionMode,
│   │                              ETriggerSource), conversation_snapshot.py (ConversationSnapshotDTO
│   │                              — reused by post_chat and get_chat responses)
│   ├── requests/                  One file per endpoint, inbound Pydantic body: post_chat.py
│   │                              (ChatRequest), post_chat_summary.py (ChatSummaryRequest);
│   │                              get_chat.py / get_chats.py are docstring-only (no request body)
│   ├── commands/                  One file per endpoint, router → service parameter object:
│   │                              post_chat.py (ProcessChatTurnCommand), get_chat.py
│   │                              (RestoreChatSessionCommand), get_chats.py
│   │                              (ListChatSessionsCommand), post_chat_summary.py
│   │                              (GenerateChatSummaryCommand)
│   ├── dto/                       One file per endpoint, service → router result object:
│   │                              post_chat.py (ChatTurnDTO), get_chat.py (ChatSessionRestoreDTO),
│   │                              get_chats.py (ChatSessionDTO — one chats-table row),
│   │                              post_chat_summary.py (ChatSummaryDTO)
│   └── responses/                 One file per endpoint, outbound Pydantic body: post_chat.py
│                                  (ChatResponse), get_chat.py (ChatChatSessionRestoreResponse),
│                                  get_chats.py (ChatSessionsResponse = list[ChatSessionDTO]),
│                                  post_chat_summary.py (ChatSummaryResponse)
│
├── db/                             PostgreSQL persistence — history layer, distinct from models/
│   ├── connection.py               AsyncEngine + async_sessionmaker lifecycle:
│   │                              create_engine_async / close_engine_async / get_session_factory /
│   │                              get_db_session_async (FastAPI dependency)
│   ├── alembic/
│   │   ├── env.py                  Alembic migration environment, reads database_url from Settings
│   │   └── versions/                993128e7e195_create_chats.py (chats table),
│   │                              2f156e1dbbc7_add_users_and_clean_chats_constraints.py
│   │                              (users table + drops the old single-owner CHECK constraint)
│   ├── orm/                        SQLAlchemy ORM — distinct from the models/ Pydantic package
│   │   ├── base.py                  Base(DeclarativeBase)
│   │   ├── user.py                  UserRow — users table (user_id, anon_id, email, timestamps)
│   │   └── chat.py                  ChatRow — chats table (session_id, anon_id, user_id, status,
│   │                              schema_version, initial_intent, collected_data/final_needs/
│   │                              borrowing_capacity JSONB, timestamps); 4 partial indexes
│   └── repositories/                Protocol + SQLAlchemy implementation per table
│       ├── user.py                  IUserRepository / SqlAlchemyUserRepository —
│       │                          get_or_create_async (resolve-or-create anon identity)
│       └── chat.py                  IChatRepository / SqlAlchemyChatRepository —
│                                  upsert_chat_snapshot_async (ON CONFLICT DO UPDATE, COALESCE
│                                  guards), list_chats_by_anon_async, get_chat_snapshot_async
│                                  (session-restore Postgres fallback, §"Session restore" above)
│
├── redis_store/                    Redis-backed persistence — session state + price cache
│   ├── client.py                   RedisClient — low-level connection pool, get_async/setex_async/
│   │                              ping_async; all Redis errors caught, logged, never propagate
│   ├── session_store.py            ISessionStore / RedisSessionStore — load_session_async /
│   │                              save_session_async, sliding 7-day TTL, key `session:{id}`
│   └── price_cache.py              RedisPriceCache — Domain API median-price cache, fixed 24h TTL,
│                                  key `price:{suburb}:{property_type}:{min_bedrooms}`
│
├── conversation/
│   ├── state_machine.py            MODULE_COMPLETION_RULES registry — merges extracted fields,
│                                  advances module, recalculates completion, owns null-safety
│                                  invariant (a non-None value is never overwritten by None);
│                                  recalculate_completion() + get_current_module() are also called
│                                  standalone by the session-restore path (completion_status and
│                                  current_module are never persisted, so both are always re-derived)
│   └── intent_router.py            Classifies each user message into a routing intent
│                                  (recommend_suburbs / list_properties / property_detail /
│                                  compare_properties / open_ended_query)
│
├── prompts/
│   ├── system_prompt_builder.py    SOLE public interface — build_extraction_prompt,
│   │                              build_question_prompt, build_system_prompt, build_summary_prompt,
│   │                              build_session_restore_prompt (Postgres-restore welcome message);
│   │                              no prompt literals outside this package
│   └── sections/                   Internal sub-package (do not import outside prompts/)
│       ├── role.py                  ROLE_DEFINITION — static assistant role block
│       ├── guardrails.py            GUARDRAIL_RULES — six compliance guardrail rules
│       ├── context.py               OWNER_OCCUPIER_CONTEXT, INVESTMENT_CONTEXT — M1 intent blocks
│       ├── instructions.py          EXTRACTION_INSTRUCTION, QUESTION_TASK_INSTRUCTION,
│       │                          SESSION_RESTORE_INSTRUCTION
│       ├── state.py                 build_state_section, build_completed_list,
│       │                          build_collected_summary, build_missing_fields
│       └── financial.py             build_borrowing_capacity_section
│
├── domain/
│   ├── llm_client.py                OpenRouter async wrapper — implements ILLMClient Protocol,
│                                  chat_with_tools_async (tool-calling) and complete_async (plain)
│   ├── borrowing_capacity.py        S-G: estimates borrowing capacity from salary data (28% DTI,
│                                  ~25yr loan, live RBA F5 rate w/ 24h cache); returns
│                                  BorrowingCapacityResult with disclaimer
│   ├── budget_gap_detector.py       S-H: compares budget_max against Domain API median price
│                                  (Redis-cached); returns BudgetGapResult, skips silently when
│                                  DOMAIN_API_KEY unset or the API call fails
│   └── user_needs_builder.py        PRD §12: assembles UserNeeds snapshot for Part 1 → Part 2 handoff
│
├── tools/
│   └── extraction_schema.py         OpenAI-format tool definition that instructs the LLM to
│                                  return structured CollectedData fields
│
├── services/                       Process orchestration layer — sequences conversation/ state
│   │                              rules, domain/ calculations + LLM gateway, and db/redis_store
│   │                              reads/writes for one HTTP operation; owns no business rule itself
│   └── chat_service.py             IChatService / ChatService — process_turn_async (POST /chat),
│                                  restore_session_async (GET /chat/{id}, Redis-or-Postgres),
│                                  generate_summary_async (POST /chat/summary)
│
├── routers/
│   ├── chat.py                      FastAPI route handlers — POST /chat, GET /chat/{session_id},
│   │                              GET /chats, POST /chat/summary; resolves dependencies, shapes
│   │                              HTTP responses, delegates all orchestration to services/chat_service.py
│   └── deps.py                      Cookie-based identity dependencies —
│                                  resolve_anon_id_async (auto-create), require_anon_id_cookie_async
│                                  (400 if missing/invalid, no auto-create)
│
├── scripts/
│   └── check_protocols.py           PAIRS registry — verifies every (Protocol, Implementation)
│                                  pair is registered; run in pre-commit + CI
│
└── tests/
    ├── conftest.py                  Shared fixtures: client_async (AsyncClient), sample_state
    ├── test_extraction_schema.py    S-A unit tests
    ├── test_state_machine.py        S-B unit tests
    ├── test_system_prompt.py        S-C unit tests
    ├── test_chat_endpoint.py        S-D integration tests (POST /chat, GET /chat/{id}, GET /chats)
    ├── test_chat_service.py         ChatService unit tests — bypasses HTTP (see test_chat_endpoint.py
    │                              for the same behaviour through the router)
    ├── test_intent_router.py        S-E unit tests
    ├── test_summary.py              S-F integration tests
    ├── test_borrowing_capacity.py   S-G unit tests
    ├── test_budget_gap_detector.py  S-H unit tests
    ├── test_session_store.py        Redis session store unit tests (mocked Redis client)
    ├── test_chat_repository.py      Postgres chat repository unit tests (upsert idempotency,
    │                              COALESCE guards, list ordering)
    ├── test_anon_id_dependency.py   Cookie identity dependency tests (auto-create, malformed
    │                              UUID, required-cookie 400 path)
    └── test_config.py               Settings validators (asyncpg prefix upgrade, empty-string→None)
```

---

## Data Flow — Single Chat Turn

```
POST /api/v1/chat  { sessionId: string | null, message: string }
    │
    ├── routers/deps.py::resolve_anon_id_async
    │       └── cookie missing/invalid → db/repositories/user.py creates a fresh users row
    │
    ├── routers/chat.py::chat_async
    │       1. redis_store/session_store.py::load_session_async(session_id)
    │              — hit → existing ConversationStateDTO; miss/None sessionId → fresh DTO
    │       2. Append user message to conversation_history
    │       ── Round 1: Extraction ──────────────────────────────────────
    │       3. build_extraction_prompt(state)  →  prompts/system_prompt_builder.py
    │       4. chat_with_tools_async()         →  domain/llm_client.py  → extracted dict
    │       5. merge_extracted_fields()        →  conversation/state_machine.py
    │       6. Recompute borrowing_capacity / budget_gap if new inputs are present
    │       ── Round 2: Question Generation ──────────────────────────────
    │       7. build_question_prompt(updated_state)  →  prompts/system_prompt_builder.py
    │       8. complete_async()               →  domain/llm_client.py  → reply str
    │       9. Append reply to conversation_history
    │       10. redis_store/session_store.py::save_session_async(state) — resets 7-day TTL
    │       11. classify_intent()  →  conversation/intent_router.py
    │       12. [new session OR any module newly completed]
    │               background_tasks.add_task(chat_repo.upsert_chat_snapshot_async, state, anon_id)
    │       13. response.set_cookie(propertyai_anon_id, ...)
    │       14. Return ChatResponse (reply + extracted + sessionId + ConversationSnapshotDTO + routing)
    │
GET /api/v1/chat/{session_id}
    ├── load_session_async → Redis hit → 200 ChatSessionRestoreResponse (resume_message: null)
    └── Redis miss → db/repositories/chat.py::get_chat_snapshot_async
            ├── Postgres miss → 404 SessionNotFoundError
            └── Postgres hit → recalculate_completion + get_current_module
                    → build_session_restore_prompt → complete_async → resume_message
                    → save_session_async (re-seeds Redis)
                    → 200 ChatSessionRestoreResponse (resume_message: <generated text>)

GET /api/v1/chats
    └── routers/deps.py::require_anon_id_cookie_async (400 if cookie missing/invalid)
            └── db/repositories/chat.py::list_chats_by_anon_async → ChatSessionDTO[] newest-first

POST /api/v1/chat/summary
    └── routers/chat.py
            Validates non-empty data, builds summary prompt, calls LLM plain completion
```

---

## Module Progression

```
EModule:  M1_PROPERTY_NEEDS → M2_LIFESTYLE → M3_SUBURB_PREFERENCE → M4_BUDGET → COMPLETE
EStatus:  IN_PROGRESS ────────────────────────────────────────────► REQUIREMENTS_COMPLETE
```

Field-level requirements live solely in `MODULE_COMPLETION_RULES` (`conversation/state_machine.py`) — see the canonical table in [CLAUDE.md](../CLAUDE.md#module-progression) and [backend-patterns.md](../.claude/rules/backend/backend-patterns.md#module-completion-rules--centralised-registry). Do not re-derive or hardcode these elsewhere.

---

## Exception Hierarchy (as-built)

```
PropertyAIException          ← base; carries status_code and details
├── LLMServiceError          ← 503 — OpenRouter / model call failures
├── StateTransitionError     ← 500 — invalid module progression
├── SummaryValidationError   ← 422 — summary requested with all-None fields
├── BadRequestError          ← 400 — business-level request validation (e.g. missing/invalid anon_id cookie)
├── RateLimitError           ← 429 — upstream LLM rate limit; includes retry_after
└── SessionNotFoundError     ← 404 — session_id absent or expired from Redis
```

A single handler in `error_handlers.py` converts every `PropertyAIException` subclass to the standard `{"error": {"code", "message", "details"}}` envelope, keyed by `status_code` on the exception instance. `RequestValidationError` (Pydantic 422) is converted by a second handler to the same envelope shape.

---

## Key Invariants

| # | Invariant | File |
|---|---|---|
| 1 | Redis holds the full, live `ConversationStateDTO`; Postgres `chats` never round-trips into a live turn — it is read-only history | `redis_store/session_store.py`, `db/repositories/chat.py` |
| 2 | `chat_repo.upsert_chat_snapshot_async` swallows and logs all exceptions — a Postgres outage must never fail a chat turn | `db/repositories/chat.py` |
| 3 | Postgres upsert only fires on new-session or module-completion turns, never on every turn | `routers/chat.py::chat_async` |
| 4 | `initial_intent` and `completed_at` are `COALESCE`-guarded — never overwritten back to `NULL` once set | `db/repositories/chat.py` |
| 5 | `resolve_anon_id_async` never fails (auto-creates); `require_anon_id_cookie_async` never auto-creates (400s instead) — do not swap these between endpoints | `routers/deps.py` |
| 5b | Session restore only re-seeds Redis after the LLM welcome-back call succeeds; a failed LLM call leaves Redis empty so the next request retries the Postgres restore path instead of caching a half-built state | `routers/chat.py::get_session_async` |
| 6 | Null-safety — a non-`None` value in `CollectedData` is never overwritten by `None` | `conversation/state_machine.py` |
| 7 | Prompt locality — all LLM prompt strings live exclusively in `prompts/system_prompt_builder.py` | `prompts/` |
| 8 | Error envelope — all 4xx/5xx responses use `{"error": {"code", "message", "details"}}` | `error_handlers.py` |
| 9 | LLM calls are always mocked in tests — no live API calls | `tests/` |
| 10 | `ChatRequest` never carries conversation state — only `session_id` and `message` | `models/requests/post_chat.py` |

Invariants 6–9 are the original P0 invariants (still in force); 1–5 and 10 are new with the persistence layer. The full project-wide invariant list lives in [CLAUDE.md](../CLAUDE.md#key-invariants).

---

## Test Coverage Targets

| Module | Target | Notes |
|---|---|---|
| `models/base.py` | 100% | `PropertyAIBaseModel` |
| `models/shared/*.py` | 100% | Enums, sub-models, `ConversationStateDTO` |
| `tools/extraction_schema.py` | 100% | |
| `conversation/state_machine.py` | 100% | |
| `conversation/intent_router.py` | 100% | Extra tests added beyond PRD spec |
| `prompts/system_prompt_builder.py` | 100% | |
| `routers/chat.py` | ≥ 80% | |
| `routers/deps.py` | ≥ 80% | Covered by `test_anon_id_dependency.py` |
| `domain/llm_client.py` | ≥ 80% | |
| `domain/borrowing_capacity.py` | ≥ 80% | |
| `domain/budget_gap_detector.py` | ≥ 80% | |
| `domain/user_needs_builder.py` | ≥ 80% | |
| `redis_store/session_store.py` | ≥ 80% | Redis client mocked — no live Redis in tests |
| `db/repositories/chat.py` | ≥ 80% | Covered by `test_chat_repository.py` |
| `db/repositories/user.py` | ≥ 80% | Covered by `test_anon_id_dependency.py` |

All LLM calls, Redis calls, and Postgres calls are mocked in tests — no live API, Redis, or database connections in the test suite.

---

## Architectural Decisions

### Intentional deviations from PRD

All deviations confirmed and documented in PRD §17 (v1.2, 19 May 2026).

| PRD | Implementation | Reason |
|---|---|---|
| `ModuleID` enum | `EModule` | Project naming convention: `E` + PascalCase |
| `SessionStatus` enum | `EStatus` | Same convention |
| `@dataclass RoutingPayload` | Pydantic `BaseModel` | Consistent with all other models; enables camelCase serialisation |
| `@property all_complete` | `@computed_field` | Required by Pydantic v2 to include computed values in serialised output |
| `chat_with_tools()` | `chat_with_tools_async()` | Project rule: all `async def` functions carry `_async` suffix |
| Intent priority in PRD table: `list_properties` before `property_detail` | Code: `property_detail` before `list_properties` | More specific pattern checked first; avoids misclassifying address-containing messages |
| `services/` package | `domain/` package | Renamed for clarity; better reflects bounded-domain responsibility |
| SA-3: `module_complete` + `user_intent` in `required` list | Not in schema; `required: []` | Two-round architecture separates extraction from control logic; module completion handled by `state_machine.py`, routing by `intent_router.py` — LLM control fields are unnecessary and add token cost |
| §2 single LLM call (reply + extraction) | Two-round LLM calls per turn | Round 1 minimal prompt for extraction accuracy; Round 2 full prompt for reply quality |
| §3 S-E `RoutingPayload` with `collected_data` | §16.3 `RoutingPayload` with `user_needs`, `execution_mode`, `agents_hint`, `triggered_at`, `trigger_source` | §16.3 supersedes the §3 definition; provides complete routing context for Part 2 |
| `SummaryResponse.structured: CollectedData` | `SummaryResponse.structured: UserNeeds` | §12 requires a full Part 1 → Part 2 handoff payload; `structured.collected` is equivalent to the original `CollectedData` |
| `SummaryRequest` (collected_data only) | `SummaryRequest` + `session_id` + `initial_intent` | `UserNeeds` snapshot requires session identity and routing intent; `initial_intent` has a default so callers need not supply it |
| `BudgetGapResult.suggested_actions: list[str]` | `tuple[str, ...]` | `BudgetGapResult` is a frozen dataclass; `tuple` is immutable and consistent with frozen semantics; JSON output is identical |
| P0: "frontend-held state, no DB writes" | Server-side Redis session store + Postgres history from this point forward | Sidebar chat history (S-P) and page-reload session restore both require server-side persistence; `ChatRequest` no longer carries `state` |
| P0: "no authentication, session_id caller-supplied" | Anonymous cookie identity (`propertyai_anon_id`) resolved server-side; `session_id` is still caller-optional but is now validated against Redis, not trusted blindly | Chat history must be scoped to a stable identity across sessions/tabs without requiring login |

### P0 scope notes (superseded — kept for history)

The original P0 record stated: *"Frontend-held state: `ConversationStateDTO` is passed in on every request and returned updated. No Redis writes in P0 (`load_state_async` / `save_state_async` raise `NotImplementedError`)"* and *"No authentication: `session_id` is caller-supplied; no validation or user binding."* **Both are now false** — see "Session & Identity Persistence Model" above. This section is retained only so the historical PRD-deviation record above remains traceable.

- **LLM gateway**: OpenRouter via `openai` SDK, model configurable via `MODEL_STRONG` env var (default `anthropic/claude-sonnet-4-5`).
- **Borrowing capacity**: Uses live RBA F5 variable rate fetched from the RBA website (24-hour cache). Falls back to `STANDARD_VARIABLE_RATE` (default 6.30%) on network failure without updating the cache. Applies a 28% DTI model on 67% net-of-tax salary.
- **Budget gap detection**: Calls the Domain API (Redis-cached, 24h TTL) for the first suburb in the user's preferred list (or commute destination if no suburbs given). Silently skips when `DOMAIN_API_KEY` is unset or the API call fails, so the main chat flow is never blocked.

---

## Dev Commands

All commands run from `backend/` unless noted.

```bash
# Install with uv (preferred)
uv sync

# One-shot: start Docker services, run pending Alembic migrations, start uvicorn --reload
uv run dev

# Dev server only (assumes Postgres/Redis already running and migrated)
uv run uvicorn main:app --reload --port 8000

# Create a new Alembic migration after changing db/orm/*.py
uv run alembic revision --autogenerate -m "description"

# Apply pending migrations manually
uv run alembic upgrade head

# Full test suite with coverage
uv run pytest

# Single test file / single test
uv run pytest tests/test_chat_repository.py
uv run pytest tests/test_state_machine.py::test_advance_on_required_fields_collected

# Lint, format check, auto-fix, type check
uv run ruff check .
uv run ruff format --check .
uv run ruff format .
uv run mypy --strict .

# Protocol/implementation registry check (required after adding a new Protocol)
uv run python scripts/check_protocols.py
```

Infrastructure (Postgres + Redis) from the repo root:

```bash
docker-compose up -d redis postgres
```

---

## Out of Scope (current)

- Streaming SSE responses
- Full user authentication / login (P1-B) — `users.user_id` and `chats.user_id` columns are reserved and unwritten until this lands; anonymous cookie identity is not a substitute for login
- Redis session persistence and PostgreSQL chat history — **removed from this list**; both are now implemented (see "Session & Identity Persistence Model")
