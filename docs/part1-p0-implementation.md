# Part 1 Conversation Layer — P0 Implementation Record

| Field | Value |
|---|---|
| PRD | PropertyAI Part 1 Technical PRD v1.1 |
| Scope | P0 — Eight stories S-A through S-H, plus PRD §12, §13, §14 |
| Status | **Complete** |
| Completed | 12 May 2026 |

---

## Story Completion

| Story | File | Tests | Status |
|---|---|---|---|
| S-A Tool Use Schema | `tools/extraction_schema.py` | `tests/test_extraction_schema.py` | Done |
| S-B Module State Machine | `conversation/state_machine.py` | `tests/test_state_machine.py` | Done |
| S-C System Prompt Builder | `prompts/system_prompt_builder.py` | `tests/test_system_prompt.py` | Done |
| S-D Chat API Endpoint | `routers/chat.py`, `domain/llm_client.py` | `tests/test_chat_endpoint.py` | Done |
| S-E Intent Router | `conversation/intent_router.py` | `tests/test_intent_router.py` | Done |
| S-F Requirements Summary | `routers/chat.py` (`/chat/summary`) | `tests/test_summary.py` | Done |
| S-G Borrowing Capacity | `domain/borrowing_capacity.py` | `tests/test_borrowing_capacity.py` | Done |
| S-H Budget Gap Detection | `domain/budget_gap_detector.py` | `tests/test_budget_gap_detector.py` | Done |
| §12 UserNeeds Output Schema | `domain/user_needs_builder.py`, `models/user_needs.py` | `tests/test_summary.py` | Done |
| §13–14 API Alignment & Error Handling | `exceptions.py`, `error_handlers.py` | `tests/test_chat_endpoint.py` | Done |

---

## E2E Acceptance Criteria

| ID | Criterion | Met |
|---|---|---|
| E2E-1 | `status == "REQUIREMENTS_COMPLETE"` after four-module conversation | ✅ |
| E2E-2 | `collectedData` contains all required fields with correct values | ✅ |
| E2E-3 | Budget data from M1 stage saved to `collectedData.m4` | ✅ |
| E2E-4 | `POST /chat/summary` returns summary covering budget, property type, commute, lifestyle | ✅ |
| E2E-5 | `ChatResponse.routing` is non-None after `all_complete` triggers | ✅ |
| E2E-6 | All unit tests pass | ✅ |
| E2E-7 | All integration tests pass | ✅ |
| E2E-8 | `SummaryResponse.structured` is a `UserNeeds` with inferred `buyer_type`, `budget_tier`, `household_profile` | ✅ |
| E2E-9 | `ConversationStateDTO.borrowing_capacity` is populated when `pre_tax_salary` is collected | ✅ |
| E2E-10 | `ConversationStateDTO.budget_gap` is populated when `budget_max` + a suburb are collected and `DOMAIN_API_KEY` is set | ✅ |
| E2E-11 | All 4xx/5xx responses use the `{"error": {"code": …, "message": …, "details": {}}}` envelope | ✅ |

---

## Architectural Decisions

### Intentional deviations from PRD

| PRD | Implementation | Reason |
|---|---|---|
| `ModuleID` enum | `EModule` | Project naming convention: `E` + PascalCase |
| `SessionStatus` enum | `EStatus` | Same convention |
| `@dataclass RoutingPayload` | Pydantic `BaseModel` | Consistent with all other models; enables camelCase serialisation |
| `@property all_complete` | `@computed_field` | Required by Pydantic v2 to include computed values in serialised output |
| `chat_with_tools()` | `chat_with_tools_async()` | Project rule: all `async def` functions carry `_async` suffix |
| Intent priority in PRD table: `list_properties` before `property_detail` | Code: `property_detail` before `list_properties` | More specific pattern checked first; avoids misclassifying address-containing messages |
| `services/` package | `domain/` package | Renamed for clarity; better reflects bounded-domain responsibility |
| `SummaryResponse.structured_data: CollectedData` | `SummaryResponse.structured: UserNeeds` | §12 requires a full Part 1 → Part 2 handoff payload, not raw collected data |
| `SummaryRequest` (collected_data only) | `SummaryRequest` + `session_id` + `initial_intent` | UserNeeds snapshot requires session identity and initial routing intent |

### P0 scope notes

- **Frontend-held state**: `ConversationStateDTO` is passed in on every request and returned updated. No Redis writes in P0 (`load_state_async` / `save_state_async` raise `NotImplementedError`).
- **No authentication**: `session_id` is caller-supplied; no validation or user binding.
- **LLM gateway**: OpenRouter via `openai` SDK, model configurable via `MODEL_STRONG` env var (default `anthropic/claude-sonnet-4-5`).
- **Borrowing capacity**: Uses live RBA F5 variable rate fetched from the RBA website (24-hour cache). Falls back to `STANDARD_VARIABLE_RATE` (default 6.30%) on network failure without updating the cache. Applies a 28% DTI model on 67% net-of-tax salary.
- **Budget gap detection**: Calls the Domain API for the first suburb in the user's preferred list (or commute destination if no suburbs given). Silently skips when `DOMAIN_API_KEY` is unset or the API call fails, so the main chat flow is never blocked.
- **Exception handling**: All business exceptions inherit `PropertyAIException` and carry an `http_status_code`. A single handler in `error_handlers.py` converts them to the standard error envelope. `RequestValidationError` (Pydantic 422) is also converted to the same envelope.

### New modules added since initial P0

| Module | Responsibility |
|---|---|
| `domain/borrowing_capacity.py` | S-G: RBA rate fetch + 28% DTI estimation, returns `BorrowingCapacityResult` |
| `domain/budget_gap_detector.py` | S-H: Domain API median price lookup, returns `BudgetGapResult` |
| `domain/user_needs_builder.py` | §12: Derives `InferredNeeds` from `CollectedData`; assembles `UserNeeds` for Part 2 handoff |
| `models/financial.py` | Frozen dataclasses `BorrowingCapacityResult` and `BudgetGapResult`; action-string constants |
| `models/user_needs.py` | `UserNeeds` and `InferredNeeds` Pydantic models (Part 1 output contract) |
| `error_handlers.py` | `register_exception_handlers()` + `configure_logging()` — centralises FastAPI error wiring |

### Exception hierarchy (as-built)

```
PropertyAIException          ← base; carries status_code and details
├── LLMServiceError          ← 503 — OpenRouter / model call failures
├── StateTransitionError     ← 500 — invalid module progression
├── SummaryValidationError   ← 422 — summary requested with all-None fields
├── BadRequestError          ← 400 — business-level request validation failures
└── RateLimitError           ← 429 — upstream LLM rate limit; includes retry_after
```

---

## Test Coverage Targets

| Module | Target | Notes |
|---|---|---|
| `models/base.py` | 100% | `PropertyAIBaseModel` |
| `models/conversation_state.py` | 100% | |
| `tools/extraction_schema.py` | 100% | |
| `conversation/state_machine.py` | 100% | |
| `conversation/intent_router.py` | 100% | Extra tests added beyond PRD spec |
| `prompts/system_prompt_builder.py` | 100% | |
| `routers/chat.py` | ≥ 80% | |
| `domain/llm_client.py` | ≥ 80% | |
| `domain/borrowing_capacity.py` | ≥ 80% | |
| `domain/budget_gap_detector.py` | ≥ 80% | |
| `domain/user_needs_builder.py` | ≥ 80% | |

All LLM calls are mocked in tests — no live API calls.

---

## Out of Scope (P1)

- Redis session persistence
- Streaming SSE responses
- User authentication
