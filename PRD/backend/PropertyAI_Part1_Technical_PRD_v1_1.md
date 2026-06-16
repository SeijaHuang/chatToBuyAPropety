# PropertyAI — Part 1 Conversation Layer

## Technical PRD v1.1

| Field           | Value                                       |
| --------------- | ------------------------------------------- |
| Version         | v1.2                                        |
| Status          | **Completed — P0 implemented and verified** |
| Parent Document | PropertyAI PRD v1.1                         |
| Scope           | Part 1 Conversation Layer — P0 + P1         |
| Last Updated    | 19 May 2026                                 |

### Changelog

| Version | Date        | Changes                                                                  |
| ------- | ----------- | ------------------------------------------------------------------------ |
| v1.0    | 3 May 2026  | 初始版本：S-A 至 S-F，P0 主链路                                          |
| v1.1    | 10 May 2026 | 新增 P0 补充章节（10–15）；新增 P1 章节（20–26）；数据库设计独立成文     |
| v1.2    | 19 May 2026 | P0 实现完成；新增 §17 Implementation Decisions，记录与原始规格的确认偏差 |

---

## Table of Contents

**原有章节（v1.0，内容不变）**

1. [Objectives and Scope](#1-objectives-and-scope)
2. [System Flow](#2-system-flow)
3. [Story Specifications](#3-story-specifications)
   - [S-A: Tool Use Schema](#s-a-tool-use-schema)
   - [S-B: Module State Machine](#s-b-module-state-machine)
   - [S-C: System Prompt Builder](#s-c-system-prompt-builder)
   - [S-D: Chat API Endpoint](#s-d-chat-api-endpoint)
   - [S-E: Intent Router](#s-e-intent-router)
   - [S-F: Requirements Summary](#s-f-requirements-summary)
4. [Data Models](#4-data-models)
5. [Database Schema](#5-database-schema)
6. [Project Structure](#6-project-structure)
7. [Test Strategy](#7-test-strategy)
8. [Environment Variables](#8-environment-variables)
9. [E2E Acceptance Criteria](#9-e2e-acceptance-criteria)

**P0 补充章节（v1.1 新增）**

10. [S-G: Borrowing Capacity Estimation](#10-s-g-borrowing-capacity-estimation)
11. [S-H: Budget Gap Detection](#11-s-h-budget-gap-detection)
12. [UserNeeds Output Schema](#12-userneeds-output-schema)
13. [API Route Overview](#13-api-route-overview)
14. [Error Handling Specification](#14-error-handling-specification)
15. [Guardrail Rule Tests](#15-guardrail-rule-tests)
16. [Part 2 Interface Contract](#16-part-2-interface-contract)
17. [Implementation Decisions](#17-implementation-decisions)

**P1-A 章节（匿名会话，v1.1 新增）**

20. [P1-A / P1-B Scope](#20-p1-a--p1-b-scope)
21. [Redis Session Persistence](#21-redis-session-persistence)
22. [SSE Streaming Response](#22-sse-streaming-response)
23. [P1-B Scope — User Accounts](#23-p1-b-scope--user-accounts)
24. [PostgreSQL Progressive Snapshot](#24-postgresql-progressive-snapshot)
25. [Budget Gap Price Cache](#25-budget-gap-price-cache)
26. [P1-A Environment Variables](#26-p1-a-environment-variables)
27. [P1-A Non-Functional Requirements](#27-p1-a-non-functional-requirements)
28. [P1-A Deployment Notes](#28-p1-a-deployment-notes)

---

## 1. Objectives and Scope

### 1.1 Objective

Implement the complete P0 main chain of the Part 1 Conversation Layer: users complete requirements collection across M1→M4 four modules through natural language dialogue, and finally output a structured `UserNeeds` JSON for Part 2 consumption.

### 1.2 In Scope (P0)

- Four-module sequential dialogue and field extraction
- Non-linear jumps (user volunteers information from any module at any time)
- Module completion detection and progression
- Dynamic system prompt generation
- Intent routing output
- Requirements summary generation
- Frontend-held state (no Redis dependency)

### 1.3 Out of Scope (P1)

- Redis session persistence
- AI guardrail rule enforcement
- Streaming SSE responses
- User authentication

---

## 2. System Flow

```
User sends message
       │
       ▼
POST /chat
       │
       ├─ 1. Load current state (passed in from frontend)
       ├─ 2. Build dynamic system prompt
       ├─ 3. Call OpenRouter (conversational reply + extract_requirements tool)
       ├─ 4. Parse tool_call, merge new fields into collectedData
       ├─ 5. Update completionStatus
       ├─ 6. Evaluate whether to trigger intent routing
       └─ 7. Return ChatResponse (including updated_state)

all_complete = true
       │
       ▼
POST /chat/summary
       │
       └─ Generate natural language requirements summary
```

---

## 3. Story Specifications

---

### S-A: Tool Use Schema

#### Objective

Define the `extract_requirements` tool schema. The LLM uses this tool to extract structured fields from user messages.

#### File

```
backend/tools/extraction_schema.py
```

#### Specification

The tool name must be `extract_requirements` (PRD §2.2.4).

All business fields are optional — the LLM only populates fields the user has clearly stated. `module_complete` and `user_intent` are required and must be returned on every invocation.

**Field groups:**

```
M1: property_type, min_bedrooms, max_bedrooms, min_bathrooms,
    min_carspaces, min_land_size, max_land_size,
    wants_pool, wants_outdoor, wants_study, intended_use

M2: household_size, has_children, needs_school_zone,
    has_pets, work_from_home, target_tenant

M3: commute_destination, commute_max_mins, commute_mode,
    preferred_suburbs, excluded_suburbs, lifestyle_vibe

M4: budget_min, budget_max, deposit_amount,
    pre_tax_salary, is_joint, partner_salary, first_home_buyer,
    loan_term_years

Control: module_complete (required), next_question, user_intent (required)
```

#### Acceptance Criteria

| ID   | Criterion                                                                                                         |
| ---- | ----------------------------------------------------------------------------------------------------------------- |
| SA-1 | Schema can be serialised by `json.dumps()` without error                                                          |
| SA-2 | `name` field value is strictly equal to `"extract_requirements"`                                                  |
| SA-3 | `module_complete` and `user_intent` are present in the `required` list                                            |
| SA-4 | All M1–M4 fields are absent from the `required` list                                                              |
| SA-5 | `property_type` enum values match PRD exactly: `["house","townhouse","unit","apartment","villa","any"]`           |
| SA-6 | `user_intent` enum values match PRD exactly: `["answering","asking_question","changing_topic","confused","done"]` |
| SA-7 | `commute_mode` enum values match PRD exactly: `["train","car","tram","bus","any"]`                                |
| SA-8 | `preferred_suburbs` and `excluded_suburbs` have type `array` with items of type `string`                          |

#### Unit Tests

```
tests/test_extraction_schema.py

test_schema_is_json_serialisable
test_tool_name_is_extract_requirements
test_required_fields_contain_module_complete_and_user_intent
test_m1_to_m4_fields_are_not_required
test_property_type_enum_values
test_user_intent_enum_values
test_commute_mode_enum_values
test_list_fields_have_correct_array_type
```

---

### S-B: Module State Machine

#### Objective

Manage M1→M4 progression logic, determine whether each module is complete, and support non-linear field reception.

#### File

```
backend/conversation/state_machine.py
```

#### Specification

**Module completion rules (minimum required fields):**

| Module | Required Fields                                   | Special Rule                                                     |
| ------ | ------------------------------------------------- | ---------------------------------------------------------------- |
| M1     | `property_type` + `min_bedrooms` + `intended_use` | All three must be non-None                                       |
| M2     | `household_size` + `has_children`                 | If `intended_use == "investment"`, also requires `target_tenant` |
| M3     | `commute_destination` + `commute_max_mins`        | Both must be non-None                                            |
| M4     | `budget_max`                                      | Must be non-None                                                 |

**`current_module` progression rule:**

Advances in order M1 → M2 → M3 → M4. Once the current module is complete, advance to the next. When all modules are complete, `status` becomes `REQUIREMENTS_COMPLETE`.

**Non-linear jump:**

`merge_extracted_fields()` accepts fields from any module and writes them to the corresponding sub-model without restricting to the current module. After merging, `completionStatus` is immediately recalculated.

**Null protection:**

Existing non-None field values must not be overwritten by incoming None values. Only non-None new values trigger an update.

#### Acceptance Criteria

| ID    | Criterion                                                                                                                     |
| ----- | ----------------------------------------------------------------------------------------------------------------------------- |
| SB-1  | When all M1 required fields are populated, `is_module_complete(M1, data)` returns `True`                                      |
| SB-2  | When any M1 required field is None, returns `False`                                                                           |
| SB-3  | When `intended_use == "investment"` and `target_tenant` is None, M2 returns `False`                                           |
| SB-4  | When `intended_use == "owner_occupier"`, M2 does not require `target_tenant`                                                  |
| SB-5  | When M1 is incomplete, `get_current_module()` returns `M1_PROPERTY_NEEDS`                                                     |
| SB-6  | When M1 is complete and M2 is incomplete, returns `M2_LIFESTYLE`                                                              |
| SB-7  | When all four modules are complete, returns `COMPLETE`                                                                        |
| SB-8  | When user provides M3 fields during M1 stage, `merge_extracted_fields()` correctly writes to `collectedData.m3` without error |
| SB-9  | After merge, `completionStatus` is immediately recalculated and correctly reflects each module's state                        |
| SB-10 | Existing non-None field values are not overwritten by incoming None values                                                    |

#### Unit Tests

```
tests/test_state_machine.py

test_m1_complete_when_all_required_fields_present
test_m1_incomplete_when_property_type_missing
test_m1_incomplete_when_min_bedrooms_missing
test_m1_incomplete_when_intended_use_missing
test_m2_requires_target_tenant_when_investment
test_m2_does_not_require_target_tenant_when_owner_occupier
test_m3_complete_when_destination_and_mins_present
test_m4_complete_when_budget_max_present
test_current_module_returns_m1_when_m1_incomplete
test_current_module_returns_m2_when_m1_complete_m2_incomplete
test_current_module_returns_complete_when_all_done
test_nonlinear_jump_writes_to_correct_submodel
test_completion_status_recalculated_after_merge
test_none_value_does_not_overwrite_existing_value
```

---

### S-C: System Prompt Builder

#### Objective

Generate a dynamic system prompt based on the current module and collected fields, corresponding to the four-section structure in PRD Appendix B.

#### File

```
backend/prompts/system_prompt_builder.py
```

#### Specification

The system prompt must contain the following four sections in fixed order:

**Section 1 — Role Definition (static)**

```
You are an AI property buying assistant for the Australian market.
Your role is to collect buyer requirements through natural conversation.
You are NOT a licensed buyer's agent, financial advisor, or legal professional.
```

**Section 2 — Current State Injection (dynamic)**

```
Current module: {current_module}
Completed modules: {completed_list}
Already collected: {collected_summary}
Missing required fields: {missing_fields}
```

**Section 3 — M1→M2 Inference Context (conditional)**

Injected only when M1 is complete. Content varies by `intended_use`:

- `owner_occupier` / `both`: focus on family structure and school zone needs
- `investment`: focus on tenant profile and rental yield priority

**Section 4 — Six Guardrail Rules Summary (static)**

Abbreviated form of all six rules from PRD §3:

```
Rule 1 — Property recommendations: present data only, never give a direct recommendation
Rule 2 — Market information: provide data, always follow with a question returning focus to user needs
Rule 3 — Budget shortfall: flag the gap directly and kindly, suggest alternatives
Rule 4 — Legal/compliance: explain concepts, refer to solicitor or conveyancer
Rule 5 — Investment predictions: historical data only, always append ASIC disclaimer
Rule 6 — Role identity: transparent explanation of AI assistant boundaries
```

#### Acceptance Criteria

| ID   | Criterion                                                                                                  |
| ---- | ---------------------------------------------------------------------------------------------------------- |
| SC-1 | Output contains all four sections in correct order                                                         |
| SC-2 | `current_module` correctly reflects the current incomplete module                                          |
| SC-3 | `collected_summary` contains fields that have values; fields not yet collected do not appear               |
| SC-4 | When M1 is incomplete, Section 3 is not present in the output                                              |
| SC-5 | When M1 is complete and `intended_use == "investment"`, Section 3 contains tenant-related guidance         |
| SC-6 | When M1 is complete and `intended_use == "owner_occupier"`, Section 3 contains family/school zone guidance |
| SC-7 | All six guardrail rules appear in the output                                                               |
| SC-8 | Output is a non-empty string with no errors raised                                                         |

#### Unit Tests

```
tests/test_system_prompt.py

test_output_contains_role_definition
test_output_contains_current_module
test_collected_summary_excludes_none_fields
test_section_3_absent_when_m1_incomplete
test_section_3_contains_tenant_guidance_for_investment
test_section_3_contains_school_guidance_for_owner_occupier
test_all_six_guardrail_rules_present
test_output_is_nonempty_string
```

---

### S-D: Chat API Endpoint

#### Objective

Implement `POST /chat`, connecting the complete chain of system prompt generation, LLM invocation, field extraction, and state update.

#### Files

```
backend/routers/chat.py
backend/services/llm_client.py
```

#### Specification

**Request / Response schema:**

```python
# Request
class ChatRequest(BaseModel):
    message: str
    state:   ConversationStateDTO

# Response
class ChatResponse(BaseModel):
    reply:         str
    extracted:     dict                        # fields extracted by tool_call
    updated_state: ConversationStateDTO
    routing:       Optional[RoutingPayload] = None
```

**Endpoint processing sequence (fixed order):**

1. Load current state from `request.state`
2. Append user message to `conversationHistory`
3. Call `build_system_prompt()`
4. Call `llm_client.chat_with_tools()`
5. Parse tool_call, call `merge_extracted_fields()`
6. Call `update_completion()`
7. Append assistant reply to `conversationHistory`
8. Call `classify_intent()` to determine whether to trigger routing
9. Return `ChatResponse`

**LLM call configuration:**

| Parameter   | Value                                                                   |
| ----------- | ----------------------------------------------------------------------- |
| Model       | `MODEL_STRONG` (`anthropic/claude-sonnet-4-5`, overridable via env var) |
| Temperature | 0.7                                                                     |
| Max tokens  | 1000                                                                    |
| Tools       | `[EXTRACT_REQUIREMENTS_TOOL]`                                           |
| Tool choice | `"auto"`                                                                |

**Error handling:**

| Scenario                  | Response                                      |
| ------------------------- | --------------------------------------------- |
| `message` is empty string | HTTP 422                                      |
| OpenRouter call fails     | HTTP 503 with clear error message             |
| LLM returns no tool_call  | `extracted: {}`, flow continues without error |

#### Acceptance Criteria

| ID   | Criterion                                                                                             |
| ---- | ----------------------------------------------------------------------------------------------------- |
| SD-1 | Valid request returns HTTP 200 with response conforming to `ChatResponse` schema                      |
| SD-2 | `updated_state.conversationHistory` contains both the user message and assistant reply from this turn |
| SD-3 | `extracted` contains fields extracted by the LLM; is `{}` when nothing is extracted                   |
| SD-4 | `updated_state.collectedData` contains fields extracted in this turn                                  |
| SD-5 | `updated_state.completionStatus` correctly reflects the latest completion state                       |
| SD-6 | When LLM returns no tool_call, `extracted` is `{}` and the flow does not raise an error               |
| SD-7 | When `message` is an empty string, returns HTTP 422                                                   |
| SD-8 | When OpenRouter call fails, returns HTTP 503 with a clear error message                               |
| SD-9 | Across multiple turns, `conversationHistory` accumulates correctly and is not reset                   |

#### Integration Tests

```
tests/test_chat_endpoint.py

test_valid_request_returns_200
test_response_conforms_to_chat_response_schema
test_conversation_history_updated_after_turn
test_extracted_fields_written_to_collected_data
test_completion_status_updated_correctly
test_no_tool_call_returns_empty_extracted
test_empty_message_returns_422
test_llm_failure_returns_503
test_history_accumulates_across_turns
```

---

### S-E: Intent Router

#### Objective

Detect requirements collection completion and classify user intent, outputting a `RoutingPayload` for Part 2.

#### File

```
backend/conversation/intent_router.py
```

#### Specification

**Trigger conditions (either):**

1. `completionStatus.all_complete == True`
2. User message matches a trigger keyword (see table below)

**Intent classification rules:**

| Intent              | Trigger Condition                                      |
| ------------------- | ------------------------------------------------------ |
| `recommend_suburbs` | Contains "suburb", "area", "recommend", "推荐", "区域" |
| `list_properties`   | Contains "property", "listing", "find", "找房", "房源" |
| `property_detail`   | Message contains a specific address or property_id     |
| `open_ended_query`  | All other cases where `all_complete` is True           |

**`RoutingPayload` definition:**

```python
@dataclass
class RoutingPayload:
    intent:         str   # one of the five intents above
    collected_data: CollectedData
    session_id:     str
```

#### Acceptance Criteria

| ID   | Criterion                                                                                      |
| ---- | ---------------------------------------------------------------------------------------------- |
| SE-1 | When `all_complete == False` and message contains no trigger keywords, returns `None`          |
| SE-2 | When `all_complete == True`, returns a non-None `RoutingPayload`                               |
| SE-3 | When message contains "recommend", `intent == "recommend_suburbs"`                             |
| SE-4 | When message contains a specific address, `intent == "property_detail"`                        |
| SE-5 | When `all_complete == True` and no explicit intent is detected, `intent == "open_ended_query"` |
| SE-6 | `RoutingPayload.collected_data` equals the current `collectedData`                             |
| SE-7 | `RoutingPayload.session_id` equals the current `sessionId`                                     |

#### Unit Tests

```
tests/test_intent_router.py

test_returns_none_when_incomplete_and_no_trigger
test_returns_payload_when_all_complete
test_recommend_intent_on_keyword_match
test_property_detail_intent_on_address_match
test_open_ended_query_as_fallback_when_complete
test_routing_payload_contains_correct_collected_data
test_routing_payload_contains_correct_session_id
```

---

### S-F: Requirements Summary

#### Objective

After all modules are complete, generate a natural language requirements summary as the terminal output of the P0 E2E chain.

#### File

```
backend/routers/chat.py  (new endpoint)
```

#### Specification

```
POST /chat/summary

Request:
  SummaryRequest { collected_data: CollectedData }

Response:
  SummaryResponse { summary_text: str, structured: CollectedData }
```

**`summary_text` requirements:**

- Covers all non-None fields across M1–M4
- Written in natural language paragraphs, not list format
- Covers four dimensions: budget, property type, location preference, lifestyle
- Language: English

**Validation:**

- If all fields in `collected_data` are None, return HTTP 422 (empty data must not generate a summary)

#### Acceptance Criteria

| ID   | Criterion                                                                 |
| ---- | ------------------------------------------------------------------------- |
| SF-1 | Valid request returns HTTP 200 with `summary_text` as a non-empty string  |
| SF-2 | `summary_text` contains the value of `budget_max` (if non-None)           |
| SF-3 | `summary_text` contains the value of `property_type` (if non-None)        |
| SF-4 | `summary_text` contains the value of `commute_destination` (if non-None)  |
| SF-5 | `structured` field equals the input `collected_data` without modification |
| SF-6 | When all fields are None, returns HTTP 422                                |

#### Integration Tests

```
tests/test_summary.py

test_valid_request_returns_200
test_summary_text_is_nonempty_string
test_summary_contains_budget_max
test_summary_contains_property_type
test_summary_contains_commute_destination
test_structured_field_unchanged
test_all_none_fields_returns_422
```

---

## 4. Data Models

All stories share the following models defined in `models/schemas.py` as the single source of truth.

### M1 — Property Needs

```python
class M1PropertyNeeds(BaseModel):
    property_type:  Optional[Literal["house","townhouse","unit","apartment","villa","any"]] = None
    min_bedrooms:   Optional[int] = None
    max_bedrooms:   Optional[int] = None
    min_bathrooms:  Optional[int] = None
    min_carspaces:  Optional[int] = None
    min_land_size:  Optional[int] = None   # sqm
    max_land_size:  Optional[int] = None   # sqm
    wants_pool:     Optional[bool] = None
    wants_outdoor:  Optional[bool] = None
    wants_study:    Optional[bool] = None
    intended_use:   Optional[Literal["owner_occupier","investment","both"]] = None
```

### M2 — Lifestyle

```python
class M2Lifestyle(BaseModel):
    household_size:    Optional[int] = None
    has_children:      Optional[bool] = None
    needs_school_zone: Optional[bool] = None
    has_pets:          Optional[bool] = None
    work_from_home:    Optional[bool] = None
    target_tenant:     Optional[Literal["family","professional","student","any"]] = None
```

### M3 — Suburb Preference

```python
class M3SuburbPreference(BaseModel):
    commute_destination: Optional[str] = None
    commute_max_mins:    Optional[int] = None
    commute_mode:        Optional[Literal["train","car","tram","bus","any"]] = None
    preferred_suburbs:   Optional[list[str]] = None
    excluded_suburbs:    Optional[list[str]] = None
    lifestyle_vibe:      Optional[Literal["inner_city","suburban","leafy","coastal","any"]] = None
```

### M4 — Budget

```python
class M4Budget(BaseModel):
    budget_min:       Optional[int] = None   # AUD
    budget_max:       Optional[int] = None   # AUD
    deposit_amount:   Optional[int] = None   # AUD
    pre_tax_salary:   Optional[int] = None   # annual pre-tax AUD
    is_joint:         Optional[bool] = None
    partner_salary:   Optional[int] = None   # AUD
    first_home_buyer: Optional[bool] = None
```

### CollectedData

```python
class CollectedData(BaseModel):
    m1: M1PropertyNeeds    = Field(default_factory=M1PropertyNeeds)
    m2: M2Lifestyle        = Field(default_factory=M2Lifestyle)
    m3: M3SuburbPreference = Field(default_factory=M3SuburbPreference)
    m4: M4Budget           = Field(default_factory=M4Budget)
```

### Session State

```python
class ModuleID(str, Enum):
    M1       = "M1_PROPERTY_NEEDS"
    M2       = "M2_LIFESTYLE"
    M3       = "M3_SUBURB_PREFERENCE"
    M4       = "M4_BUDGET"
    COMPLETE = "COMPLETE"

class SessionStatus(str, Enum):
    IN_PROGRESS           = "IN_PROGRESS"
    REQUIREMENTS_COMPLETE = "REQUIREMENTS_COMPLETE"

class CompletionStatus(BaseModel):
    M1: bool = False
    M2: bool = False
    M3: bool = False
    M4: bool = False

    @property
    def all_complete(self) -> bool:
        return self.M1 and self.M2 and self.M3 and self.M4

    @property
    def current_module(self) -> ModuleID:
        for mid, done in [
            (ModuleID.M1, self.M1),
            (ModuleID.M2, self.M2),
            (ModuleID.M3, self.M3),
            (ModuleID.M4, self.M4),
        ]:
            if not done:
                return mid
        return ModuleID.COMPLETE

class ConversationStateDTO(BaseModel):
    sessionId:           str
    status:              SessionStatus      = SessionStatus.IN_PROGRESS
    currentModule:       ModuleID           = ModuleID.M1
    completionStatus:    CompletionStatus   = Field(default_factory=CompletionStatus)
    collectedData:       CollectedData      = Field(default_factory=CollectedData)
    conversationHistory: list[dict]         = Field(default_factory=list)
    finalNeeds:          Optional[CollectedData] = None
```

### Routing

```python
@dataclass
class RoutingPayload:
    intent:         str
    collected_data: CollectedData
    session_id:     str
```

---

## 5. Database Schema

> P1 maintains a single `sessions` table. The `users` table and `user_id` foreign key are P2 features; they will be added as additive column additions at that point without modifying this schema.
>
> `session_id` uses PostgreSQL's native `UUID` type. The frontend generates the value as a UUID v4 string; PostgreSQL accepts and stores it as a 16-byte native UUID (more efficient than `TEXT` at 36 bytes, with built-in format validation).

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id         UUID        PRIMARY KEY,
    status             TEXT        NOT NULL DEFAULT 'IN_PROGRESS',
    schema_version     TEXT        NOT NULL DEFAULT '1.1',
    initial_intent     TEXT,
    collected_data     JSONB       NOT NULL,
    final_needs        JSONB,
    borrowing_capacity JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sessions_status
    ON sessions (status);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
    ON sessions (updated_at DESC);
```

| Column               | Type        | Nullable | Description                                                                                  |
| -------------------- | ----------- | -------- | -------------------------------------------------------------------------------------------- |
| `session_id`         | UUID        | No       | UUID v4 generated by the frontend; primary key                                               |
| `status`             | TEXT        | No       | `IN_PROGRESS` / `REQUIREMENTS_COMPLETE`                                                      |
| `schema_version`     | TEXT        | No       | Fixed at `'1.1'` for current schema                                                          |
| `initial_intent`     | TEXT        | Yes      | Written on first M1 completion                                                               |
| `collected_data`     | JSONB       | No       | Cumulative snapshot of all collected fields across M1–M4                                     |
| `final_needs`        | JSONB       | Yes      | Full `UserNeeds` written after M4 completion                                                 |
| `borrowing_capacity` | JSONB       | Yes      | Borrowing capacity estimate written after M4 completion                                      |
| `created_at`         | TIMESTAMPTZ | No       | Auto-set on first insert                                                                     |
| `updated_at`         | TIMESTAMPTZ | No       | Updated on every upsert                                                                      |
| `completed_at`       | TIMESTAMPTZ | Yes      | Set when `status` transitions to `REQUIREMENTS_COMPLETE`; used for completion-rate analytics |

**Not persisted to the database:** `conversation_history` (large unbounded text, not structured business data) and `budget_gap` (derived value — its inputs are already in `collected_data` and can be recomputed on demand). Full write rules are specified in §27.

---

## 6. Project Structure

```
backend/
├── main.py
├── models/
│   └── schemas.py                    # Single source of truth: all Pydantic models
├── tools/
│   └── extraction_schema.py          # S-A: extract_requirements tool definition
├── conversation/
│   ├── state_machine.py              # S-B: module progression logic
│   └── intent_router.py             # S-E: intent classification and routing
├── prompts/
│   └── system_prompt_builder.py      # S-C: dynamic system prompt generation
├── services/
│   └── llm_client.py                 # S-D: OpenRouter wrapper
├── routers/
│   └── chat.py                       # S-D + S-F: /chat and /chat/summary endpoints
└── tests/
    ├── test_extraction_schema.py      # S-A unit tests
    ├── test_state_machine.py          # S-B unit tests
    ├── test_system_prompt.py          # S-C unit tests
    ├── test_chat_endpoint.py          # S-D integration tests
    ├── test_intent_router.py          # S-E unit tests
    └── test_summary.py               # S-F integration tests
```

---

## 7. Test Strategy

### 7.1 Unit Tests (no external dependencies)

Cover S-A, S-B, S-C, S-E using `pytest`. No LLM mocking required.

```python
# Example: S-B unit test
def test_m1_complete_when_all_required_fields_present():
    data = CollectedData(m1=M1PropertyNeeds(
        property_type="house",
        min_bedrooms=3,
        intended_use="owner_occupier"
    ))
    assert is_module_complete(ModuleID.M1, data) == True

def test_m2_requires_target_tenant_for_investment():
    data = CollectedData(
        m1=M1PropertyNeeds(intended_use="investment"),
        m2=M2Lifestyle(household_size=1, has_children=False)
    )
    assert is_module_complete(ModuleID.M2, data) == False
```

### 7.2 Integration Tests (mocked LLM)

Cover S-D and S-F using `pytest` + `httpx.AsyncClient` + `unittest.mock`. Mock `llm_client.chat_with_tools()` to return preset values.

```python
# Example: S-D integration test
@pytest.mark.asyncio
async def test_chat_endpoint_returns_updated_state(mock_llm):
    mock_llm.return_value = (
        "Great, tell me about your lifestyle.",
        {
            "property_type": "house",
            "min_bedrooms": 3,
            "module_complete": False,
            "user_intent": "answering"
        }
    )
    response = await client.post("/chat", json={...})
    assert response.status_code == 200
    data = response.json()
    assert data["updated_state"]["collectedData"]["m1"]["property_type"] == "house"
```

### 7.3 E2E Test (full chain)

One complete four-module conversation test. Mock LLM returns a preset sequence. Validates the full flow from M1 through to summary generation.

```python
async def test_full_conversation_e2e():
    # Turn 1: M1 information
    # Turn 2: M2 information
    # Turn 3: M3 information
    # Turn 4: M4 information → all_complete = True
    # Turn 5: POST /chat/summary → returns summary
    ...
    assert final_state["status"] == "REQUIREMENTS_COMPLETE"
    assert summary["summary_text"] != ""
```

### 7.4 Test Coverage Target

| Layer                              | Target Coverage |
| ---------------------------------- | --------------- |
| `models/schemas.py`                | 100%            |
| `tools/extraction_schema.py`       | 100%            |
| `conversation/state_machine.py`    | 100%            |
| `conversation/intent_router.py`    | 100%            |
| `prompts/system_prompt_builder.py` | 100%            |
| `routers/chat.py`                  | ≥ 80%           |
| `services/llm_client.py`           | ≥ 80%           |

---

## 8. Environment Variables

| Variable                 | Required | Default                       | Description                                      |
| ------------------------ | -------- | ----------------------------- | ------------------------------------------------ |
| `OPENROUTER_API_KEY`     | Yes      | —                             | OpenRouter API key                               |
| `MODEL_STRONG`           | No       | `anthropic/claude-sonnet-4-5` | Model for conversation turns                     |
| `MODEL_FAST`             | No       | `anthropic/claude-haiku-4-5`  | Model for lightweight extraction                 |
| `STANDARD_VARIABLE_RATE` | No       | `6.30`                        | Fallback 年利率（%），RBA F5 不可用时使用（S-G） |
| `DEFAULT_LOAN_TERM`      | No       | `30`                          | 默认贷款年限（年）（S-G）                        |

---

## 9. E2E Acceptance Criteria

The P0 implementation is considered complete when all of the following are satisfied:

| ID    | Criterion                                                                                           |
| ----- | --------------------------------------------------------------------------------------------------- |
| E2E-1 | After completing the four-module conversation, `status == "REQUIREMENTS_COMPLETE"`                  |
| E2E-2 | `collectedData` contains all required fields from all four modules with correct values              |
| E2E-3 | Budget information volunteered by the user during M1 stage is correctly saved to `collectedData.m4` |
| E2E-4 | `POST /chat/summary` returns a summary covering budget, property type, commute, and lifestyle       |
| E2E-5 | `ChatResponse.routing` is non-None after `all_complete` is triggered                                |
| E2E-6 | All unit tests pass (0 failures)                                                                    |
| E2E-7 | All integration tests pass (0 failures)                                                             |

---

# P0 补充章节（v1.1 新增）

> 以下章节为 v1.1 新增内容，补充 v1.0 中缺失的 P0 规格。原有章节 §1–§9 内容不变。

---

## 10. S-G: Borrowing Capacity Estimation

### Objective

当 M4 收集到薪资数据后，自动计算借款能力估算值，供对话 AI 在回应中引用。估算结果仅作参考，不构成金融建议（对应守卫规则 5）。

### File

```
backend/services/borrowing_capacity.py
```

### Specification

#### 参考利率 — RBA F5 + Fallback 机制

利率在应用启动时从 RBA F5 统计表（Indicator Lending Rates）获取，结果缓存 24 小时。若 fetch 失败，则回退至环境变量默认值。

```python
F5_CSV_URL      = "https://www.rba.gov.au/statistics/tables/csv/f5-data.csv"
F5_TARGET_FIELD = "FILRHLBVD"  # Lending rates; Housing loans; Banks; Variable; Discounted; Owner-occupier

async def get_reference_rate() -> tuple[float, str]:
    """
    返回 (年利率%, 利率来源描述)。
    启动时获取并缓存，TTL 24 小时。
    """
    try:
        resp = await httpx.AsyncClient().get(F5_CSV_URL, timeout=5.0)
        rate = _parse_f5_latest(resp.text, series_id=F5_TARGET_FIELD)
        source = f"RBA F5 浮动折扣自住利率 {rate:.2f}% p.a."
        return (rate, source)
    except Exception:
        fallback = float(os.getenv("STANDARD_VARIABLE_RATE", "6.30"))
        source = f"参考利率 {fallback:.2f}% p.a.（RBA F5 暂时不可用）"
        return (fallback, source)
```

> F5 已反映实际银行住房贷款利率，无需额外加利差。
> `_parse_f5_latest()` 需跳过 CSV 头部 metadata 行，定位 `FILRHLBVD` 系列，并返回最新非空值。

#### 计算公式

```python
DTI_LIMIT    = float(os.getenv("BORROWING_CAPACITY_DTI", "0.28"))
DEFAULT_TERM = int(os.getenv("DEFAULT_LOAN_TERM", "30"))

def _annuity_factor(annual_rate_pct: float, years: int) -> float:
    """标准等额还款年金因子（正确摊销公式，替代原简化因子）。"""
    r = annual_rate_pct / 100 / 12   # 月利率
    n = years * 12                    # 还款总期数
    return (1 - (1 + r) ** -n) / r

async def estimate_borrowing_capacity(m4: M4Budget) -> Optional[BorrowingCapacityResult]:
    if m4.pre_tax_salary is None:
        return None

    annual_rate, rate_source = await get_reference_rate()
    loan_term = m4.loan_term_years or DEFAULT_TERM

    # 保守税后月收入估算（有效税率约 33%）
    net_monthly = (m4.pre_tax_salary * 0.67) / 12
    if m4.is_joint and m4.partner_salary:
        net_monthly += (m4.partner_salary * 0.67) / 12

    max_monthly_repayment = net_monthly * DTI_LIMIT
    raw_capacity          = max_monthly_repayment * _annuity_factor(annual_rate, loan_term)
    estimated_capacity    = round(raw_capacity / 10_000) * 10_000

    disclaimer = (
        f"此借款能力估算基于{rate_source}、"
        f"{loan_term} 年贷款期限及 {DTI_LIMIT*100:.0f}% 月收入还款上限，仅供参考。"
        f"实际可贷金额因银行政策、现有债务、LVR 及个人信用状况而异。"
        f"请咨询持牌贷款经纪人或银行获取准确评估。"
    )

    return BorrowingCapacityResult(
        estimated_capacity = estimated_capacity,
        monthly_repayment  = int(max_monthly_repayment),
        based_on_salary    = m4.pre_tax_salary + (m4.partner_salary or 0),
        is_joint           = bool(m4.is_joint and m4.partner_salary),
        annual_rate        = annual_rate,
        loan_term_years    = loan_term,
        rate_source        = rate_source,
        disclaimer         = disclaimer,
    )
```

**触发条件：** M4 模块中 `pre_tax_salary` 字段变为非 None 时自动触发。

#### 输出结构

```python
@dataclass
class BorrowingCapacityResult:
    estimated_capacity: int    # AUD，四舍五入至最近 $10,000
    monthly_repayment:  int    # AUD/月（计算中使用的月还款上限）
    based_on_salary:    int    # 用于计算的税前薪资总额（单人或合计）
    is_joint:           bool
    annual_rate:        float  # 实际使用的年利率（%）
    loan_term_years:    int    # 实际使用的贷款年限（年）
    rate_source:        str    # 利率来源描述，注入免责声明
    disclaimer:         str    # 必须非空，注入 AI 回复
```

#### M4Budget 及 Extraction Schema 变更

`M4Budget` 新增一个可选字段（同步添加至 S-A extraction schema，供 LLM 从对话中提取用户偏好）：

```python
loan_term_years: Optional[int] = None  # 用户期望的贷款年限（年）
```

#### 环境变量

以下变量补充至 §8 / §24：

| 变量                     | 默认值 | 说明                                      |
| ------------------------ | ------ | ----------------------------------------- |
| `STANDARD_VARIABLE_RATE` | `6.30` | Fallback 年利率（%），RBA F5 不可用时使用 |
| `DEFAULT_LOAN_TERM`      | `30`   | 默认贷款年限（年）                        |

原有变量 `BORROWING_CAPACITY_DTI`（默认值 `0.28`）保持不变。

### Acceptance Criteria

| ID   | Criterion                                                                                                    |
| ---- | ------------------------------------------------------------------------------------------------------------ |
| SG-1 | 单人税前 $100,000 → `estimated_capacity` 在 **$230,000–$270,000** 区间（基于 F5 约 6.30%、30 年期、28% DTI） |
| SG-2 | 双人合计税前 $200,000 → `estimated_capacity` 约为单人的 2 倍                                                 |
| SG-3 | `pre_tax_salary` 为 None 时，函数返回 None，不抛出异常                                                       |
| SG-4 | `disclaimer` 为非空字符串，且包含实际使用的利率数值和贷款年限                                                |
| SG-5 | `estimated_capacity` 四舍五入至最近 $10,000                                                                  |
| SG-6 | RBA F5 fetch 失败时，`rate_source` 包含"暂时不可用"字样，函数仍返回有效结果                                  |
| SG-7 | 传入 `loan_term_years=25` 时，`estimated_capacity` 低于同薪资 `loan_term_years=30` 的结果                    |

### Unit Tests

```
tests/test_borrowing_capacity.py

test_single_income_calculation
test_joint_income_calculation
test_returns_none_when_salary_is_none
test_disclaimer_contains_rate_and_term
test_capacity_rounded_to_nearest_ten_thousand
test_rba_fetch_failure_returns_fallback_result
test_shorter_loan_term_produces_lower_capacity
```

---

## 11. S-H: Budget Gap Detection

### Objective

当 `budget_max` 明显低于目标区域市场中位价时，向对话 AI 注入预算缺口上下文，驱动 AI 主动依照守卫规则 3 告知用户。

### File

```
backend/services/budget_gap_detector.py
```

### Specification

**触发条件（同时满足）：**

1. `budget_max` 非 None
2. `preferred_suburbs` 非空 OR `commute_destination` 已填写

**检测逻辑：**

```python
async def detect_budget_gap(
    budget_max: int,
    property_type: str,
    min_bedrooms: int,
    suburbs: list[str]
) -> Optional[BudgetGapResult]:
    # 查询 Domain API 获取中位价
    # 若 budget_max < median_price * 0.85（缺口 > 15%），触发提示
```

**输出结构：**

```python
@dataclass
class BudgetGapResult:
    has_gap:           bool
    budget_max:        int
    market_median:     int
    gap_amount:        int       # market_median - budget_max
    gap_percentage:    float     # (gap_amount / market_median) * 100
    reference_suburb:  str
    suggested_actions: list[str] # 至少 2 项：explore_nearby_suburbs / adjust_property_type / revisit_budget
```

**系统提示注入（检测到缺口时追加至 Section 2）：**

```
⚠️ Budget Gap Detected:
  User budget: ${budget_max:,}
  Market median ({property_type}, {bedrooms}br, {suburb}): ${market_median:,}
  Gap: ${gap_amount:,} ({gap_percentage:.0f}%)
  Action required: Flag this gap directly and kindly. Suggest alternatives per Rule 3.
```

### Acceptance Criteria

| ID   | Criterion                                                     |
| ---- | ------------------------------------------------------------- |
| SH-1 | 缺口 > 15% 时，`has_gap` 为 True                              |
| SH-2 | 缺口 ≤ 15% 时，`has_gap` 为 False，不注入提示                 |
| SH-3 | Domain API 调用失败时，返回 None，不阻断主流程                |
| SH-4 | `suggested_actions` 列表始终包含至少 2 个选项                 |
| SH-5 | 注入内容存在时，系统提示 Section 2 包含 "Budget Gap Detected" |

### Unit Tests

```
tests/test_budget_gap_detector.py

test_gap_detected_when_over_15_percent
test_no_gap_within_threshold
test_returns_none_when_api_fails
test_suggested_actions_minimum_count
test_system_prompt_includes_gap_warning
```

---

## 12. UserNeeds Output Schema

> 补充 §4 Data Models，定义 Part 1 最终输出给 Part 2 的标准 JSON 结构。§4 原有模型不变，本章为新增模型。

### 12.1 UserNeeds（Part 1 → Part 2 接口契约）

```python
class UserNeeds(BaseModel):
    # 元数据
    session_id:      str
    generated_at:    datetime
    schema_version:  str = "1.1"

    # 核心需求（来自 CollectedData，直接透传给 Part 2）
    collected:       CollectedData

    # 触发 Part 2 时用户的意图
    initial_intent:  EUserIntent  # recommend_suburbs | list_properties | property_detail | open_ended_query
```

---

## 13. API Route Overview

> 补充 §6 Project Structure，提供完整 P0 端点清单。

### P0 Endpoints

| Method | Path            | Story | Description                       |
| ------ | --------------- | ----- | --------------------------------- |
| `POST` | `/chat`         | S-D   | 发送消息，返回 AI 回复 + 状态更新 |
| `POST` | `/chat/summary` | S-F   | 生成自然语言需求摘要              |
| `GET`  | `/health`       | —     | 健康检查                          |

### P0 Request / Response（完整定义）

```python
# POST /chat
class ChatRequest(BaseModel):
    message: str
    state:   ConversationStateDTO    # P0：前端传入完整状态

class ChatResponse(BaseModel):
    reply:         str
    extracted:     dict
    updated_state: ConversationStateDTO
    routing:       Optional[RoutingPayload] = None

# POST /chat/summary
class SummaryRequest(BaseModel):
    collected_data: CollectedData

class SummaryResponse(BaseModel):
    summary_text: str
    structured:   CollectedData
```

> P1 接口变更见 §21。

---

## 14. Error Handling Specification

> 补充 S-D 中的错误处理表，扩展为 P0 全局规范。

### 14.1 HTTP 错误码

| HTTP Code | 场景                                               | 返回格式                                        |
| --------- | -------------------------------------------------- | ----------------------------------------------- |
| `400`     | 请求参数格式错误（非验证错误）                     | `{"error": "bad_request", "detail": "..."}`     |
| `422`     | Pydantic 验证失败（空 message、空 collected_data） | FastAPI 默认格式                                |
| `429`     | OpenRouter 速率限制                                | `{"error": "rate_limited", "retry_after": 2}`   |
| `503`     | OpenRouter 调用失败 / 超时                         | `{"error": "llm_unavailable", "detail": "..."}` |

### 14.2 LLM 调用降级策略

```
OpenRouter 调用失败
       │
       ├─ 重试次数 < 2 → exponential backoff (0.5s → 1s) → 重试
       └─ 重试耗尽 → 返回 503
```

### 14.3 Tool Call 解析容错

```python
try:
    extracted = parse_tool_call(response)
except (JSONDecodeError, ValidationError) as e:
    logger.warning(f"Tool call parse failed: {e}")
    extracted = {}    # 降级为空提取，对话流程继续，不返回 5xx
```

---

## 15. Guardrail Rule Tests

> 补充 §7 Test Strategy，新增六条守卫规则的专项测试。测试方式为 Mock LLM 调用，验证系统提示注入的完整性，不测试 LLM 输出内容本身。

```
tests/test_guardrail_rules.py
```

| 测试名称                               | 对应规则 | 触发输入                      | 期望行为                                       |
| -------------------------------------- | -------- | ----------------------------- | ---------------------------------------------- |
| `test_rule1_no_direct_recommendation`  | Rule 1   | "你推荐我买哪个房子？"        | 系统提示含 Rule 1 约束；回复不含直接推荐       |
| `test_rule2_market_data_with_followup` | Rule 2   | "Hawthorn 三房中位价是多少？" | 系统提示含 Rule 2 约束；回复含数据 + 跟进问题  |
| `test_rule3_budget_gap_flagged`        | Rule 3   | budget=$500k，Hawthorn 3br    | 系统提示注入 Budget Gap；回复含缺口告知        |
| `test_rule4_legal_redirected`          | Rule 4   | "这份合同有没有问题？"        | 系统提示含 Rule 4 约束；回复含转介专业人士     |
| `test_rule5_no_investment_prediction`  | Rule 5   | "这个区域会涨价吗？"          | 系统提示含 Rule 5 约束；回复含 ASIC 免责声明   |
| `test_rule6_identity_transparent`      | Rule 6   | "你是真正的买家代理吗？"      | 系统提示含 Rule 6 约束；回复含 AI 助手身份说明 |

---

## 16. Part 2 Interface Contract

> 定义 Part 1 → Part 2 的数据传递规范。

### 16.1 触发时机

| 触发方式   | 条件                                                                       |
| ---------- | -------------------------------------------------------------------------- |
| 自动触发   | `all_complete == True` 且 `user_intent` 为 `"done"` 或 `"answering"`       |
| 关键词触发 | 用户消息含意图关键词（见 S-E），即便未完成所有模块也可触发（携带部分数据） |
| 手动触发   | 用户点击前端"查看推荐"→ 前端调用 `POST /chat/trigger-routing`              |

### 16.2 传递方式

| 阶段  | 传递方式                                                                                                                                         |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| P0    | `ChatResponse.routing` 内嵌 `RoutingPayload`，前端负责转发给 Part 2 API                                                                         |
| P1-A  | `ChatResponse.routing` 继续内嵌（供前端判断触发条件）；`UserNeeds` 同时写入 PostgreSQL `sessions.final_needs`，Part 2 直接查库，无需前端转发数据 |
| P2    | Part 2 按需决定缓存策略；`routing:{session_id}` Redis key 不在 P1-A 实现范围内                                                                   |

### 16.3 RoutingPayload 完整定义（v1.1 更新）

```python
@dataclass
class RoutingPayload:
    intent:         str                        # 来自 S-E 意图分类
    session_id:     str
    user_needs:     UserNeeds                  # 见 §12
    execution_mode: EExecutionMode
                    # code_driven  = 已知 intent，直接派发 agent
                    # agentic_loop = open_ended_query，LLM 编排 agents
    agents_hint:    list[str]                  # Mode A 建议调用的 agent 列表
    triggered_at:   datetime
    trigger_source: Literal["auto_complete", "keyword", "manual"]
```

### 16.4 agents_hint 映射表

| Intent               | Mode           | agents_hint                                                                                                    |
| -------------------- | -------------- | -------------------------------------------------------------------------------------------------------------- |
| `recommend_suburbs`  | `code_driven`  | `["suburb_agent", "price_agent"]`                                                                              |
| `list_properties`    | `code_driven`  | `["suburb_agent", "price_agent"]`                                                                              |
| `property_detail`    | `code_driven`  | `["overlay_agent", "school_agent", "building_agent", "price_agent", "neighbourhood_agent", "transport_agent"]` |
| `compare_properties` | `code_driven`  | `["price_agent", "overlay_agent", "school_agent", "building_agent", "neighbourhood_agent", "transport_agent"]` |
| `open_ended_query`   | `agentic_loop` | `[]`（LLM 自主决定）                                                                                           |

---

## 17. Implementation Decisions

> 本章记录 P0 实现过程中，经过评审确认的与原始规格的偏差。所有条目均为**有意的设计决策**，不视为缺陷。

---

### 17.1 提取工具 Schema 不包含控制字段（原 SA-3）

**原始规格：** SA-3 要求 `module_complete` 和 `user_intent` 作为 `required` 字段存在于 `extract_requirements` tool schema 中，`user_intent` 枚举值为 `["answering","asking_question","changing_topic","confused","done"]`。

**实际实现：** 提取工具 schema 的 `required` 列表为空，`module_complete`、`user_intent`、`next_question` 三个控制字段均未定义在 schema 中。

**原因：** 原始规格基于**单轮对话**模型设计——一次 LLM 调用同时完成字段提取和控制逻辑，因此需要 LLM 返回控制字段。实际实现采用**双轮对话**架构（见 17.5），两者分离：

- 模块推进 → `conversation/state_machine.py` 的规则引擎（`recalculate_completion()`）
- 路由意图 → `conversation/intent_router.py` 的关键词匹配

控制字段在双轮架构中无意义，移除后可减少 token 消耗并提升稳定性（规则引擎结果确定，不依赖 LLM 判断）。

---

### 17.2 SummaryResponse.structured 返回 UserNeeds 而非 CollectedData（原 §13）

**原始规格：** `SummaryResponse { summary_text: str, structured: CollectedData }`

**实际实现：** `SummaryResponse { summary_text: str, structured: UserNeeds }`

**原因：** `UserNeeds` 是 Part 1 → Part 2 的标准接口契约（§12），包含 `session_id`、`generated_at`、`schema_version`、`collected`、`initial_intent`。在 summary 端点直接返回 `UserNeeds` 使前端可以直接用于触发 Part 2，无需额外封装。`structured.collected` 等价于原来的 `CollectedData`，信息不丢失。

---

### 17.3 SummaryRequest 包含额外字段（原 §13）

**原始规格：** `SummaryRequest { collected_data: CollectedData }`

**实际实现：** `SummaryRequest { collected_data: CollectedData, session_id: str, initial_intent: EUserIntent }`

**原因：** 构建 `UserNeeds`（见 17.2）需要 `session_id` 和 `initial_intent`。`initial_intent` 有默认值 `open_ended_query`，调用方可不传。

---

### 17.4 RoutingPayload 采用 §16.3 定义（原 §3 S-E）

**原始规格（§3 S-E）：**

```python
@dataclass
class RoutingPayload:
    intent: str
    collected_data: CollectedData
    session_id: str
```

**实际实现（§16.3）：**

```python
class RoutingPayload:
    intent: EUserIntent
    session_id: str
    user_needs: UserNeeds
    execution_mode: EExecutionMode
    agents_hint: list[str]
    triggered_at: datetime
    trigger_source: ETriggerSource
```

**原因：** §16.3 是 v1.1 的后期修订，为 Part 2 提供更完整的路由上下文。`user_needs.collected` 等价于原来的 `collected_data`。§3 S-E 的原始定义视为被 §16.3 supersede。

---

### 17.5 双轮 LLM 调用架构（原 §2 系统流程）

**原始规格：** §2 流程图暗示一次 LLM 调用同时完成"对话回复 + 字段提取"。

**实际实现：** 每个 `/chat` 请求发起两次 LLM 调用：

- **Round 1（Extraction）：** 使用最小化 system prompt + `extract_requirements` tool，提取结构化字段
- **Round 2（Question Generation）：** 使用完整 system prompt（含角色定义、状态、守卫规则），生成对话回复

**原因：** 单轮调用中 tool_call 和文本回复共用同一 system prompt，难以同时优化提取准确性和回复质量。双轮分离后：Round 1 专注提取（minimal prompt 减少干扰），Round 2 专注对话（full prompt 保证质量）。代价是每次请求多一次 LLM 调用。

---

### 17.6 ConversationStateDTO 携带 S-G/S-H 计算结果（原 §4）

**原始规格：** §4 的 `ConversationStateDTO` 不包含 `borrowing_capacity` 和 `budget_gap`。

**实际实现：** 新增两个可选字段：

```python
borrowing_capacity: BorrowingCapacityResult | None = None
budget_gap: BudgetGapResult | None = None
```

**原因：** P0 为前端持有状态架构，S-G/S-H 的计算结果需要随 state 一起返回给前端，再由前端在下一轮请求中回传，以便 `build_question_prompt()` 注入借款能力和预算缺口上下文。将这两个字段挂在 DTO 上是最自然的传递路径。

---

### 17.7 BudgetGapResult.suggested_actions 类型为 tuple 而非 list（原 §11）

**原始规格：** `suggested_actions: list[str]`

**实际实现：** `suggested_actions: tuple[str, ...]`

**原因：** `BudgetGapResult` 是 `@dataclass(frozen=True)`，冻结语义要求字段不可变。`list` 可变，`tuple` 不可变，后者与 frozen dataclass 语义一致。JSON 序列化输出相同（均为数组），对调用方无影响。

---

# P1 章节（v1.1 新增）

> 以下章节描述 P1 阶段新增功能的技术规格。P1 在 P0 主链路完成并稳定后实施。

---

## 20. P1-A / P1-B Scope

### 20.1 P1-A In Scope（匿名会话，当前实现）

| 功能                   | 优先级 | 依赖                        | 说明                                                              |
| ---------------------- | ------ | --------------------------- | ----------------------------------------------------------------- |
| Redis 会话持久化       | 高     | Redis 容器                  | 替换前端持有状态；支持会话跨标签/服务端重启恢复；见 §21           |
| PostgreSQL 渐进快照    | 高     | PostgreSQL 容器             | M1→M4 每模块完成时异步 upsert，防 Redis TTL 过期数据丢失；见 §24  |
| Budget Gap Price Cache | 高     | Redis                       | Domain API 郊区中位价缓存 24h，避免重复调用；见 §25               |
| SSE 流式响应           | 中     | FastAPI EventSourceResponse | 改善首字延迟，目标 < 1s 首 token                                  |
| Prompt Cache           | 低     | httpx 或 Anthropic SDK      | 系统提示静态部分 cache，降低 token 成本                           |

### 20.2 P1-A Out of Scope

以下功能 P1-A **不实现**，推迟至 P1-B 或 P2：

- **用户账户 / 认证**：无注册、登录、JWT；"用户"等价于"持有 session_id 的浏览器"
- **SESSION_SECRET_KEY**：无需签名，P1-A session_id 为不可猜的 UUID v4
- **browser_fp（浏览器指纹）**：无匿名身份绑定，ChatRequest 只含 `session_id` + `message`
- **用户画像持久化**：跨 session 预填 CollectedData 需要用户身份，P1-A 不支持
- **Session 历史列表**：类 Claude.ai 对话历史，需用户账户关联，P1-B 实现
- **Redis `routing:{session_id}` key**：Part 2 直接查 PostgreSQL `sessions.final_needs`；见 §16.2
- **DELETE /session 端点**：Redis TTL 自然过期，无需主动删除
- Crime Agent、Development Agent 等 Phase 2 agents
- 多城市扩展（Sydney、Brisbane）
- 报告导出 PDF / 浏览器插件

### 20.3 P1-B Scope（规划中，不在当前 PRD 范围）

P1-B 在 P1-A 基础上引入用户账户体系，主要包含：

| 功能             | 说明                                              |
| ---------------- | ------------------------------------------------- |
| 用户注册 / 登录  | 邮箱 + 密码或 OAuth（Google）                     |
| JWT 认证         | `SESSION_SECRET_KEY` 签发 token，保护会话端点     |
| 用户画像持久化   | 跨 session 保存 CollectedData，新 session 预填    |
| Session 历史列表 | `user:{user_id}:sessions` ZSET + 自动生成 title   |
| 匿名 → 账户迁移  | 注册时将现有 session_id 绑定至新账户              |

> P1-B 设计文档待另立，本 PRD 不展开。

---

## 21. Redis Session Persistence

> P1 实现。替换 P0 的前端持有状态方案。

### 21.1 P0 vs P1 状态存储对比

| 维度         | P0（前端持有）     | P1（Redis 持久化）                 |
| ------------ | ------------------ | ---------------------------------- |
| 存储位置     | 前端 `useState`    | Redis `session:{session_id}`       |
| 跨标签/设备  | 不支持             | 支持                               |
| 服务端重启后 | 丢失               | 保留（TTL 7 天）                   |
| 接口变化     | `state` 随请求传入 | 服务端按 session_id 自动加载       |
| 并发安全     | 前端单线程安全     | 需 Redis 原子操作（WATCH + MULTI） |

### 21.2 Redis Key Schema

P1 中 Redis 存两类数据，前缀不重叠、互不干扰：

| Key 前缀   | 类型               | 用途                            | TTL 策略                     |
| ---------- | ------------------ | ------------------------------- | ---------------------------- |
| `session:` | Session Store      | `ConversationStateDTO` 工作内存 | 滑动窗口，7 天，每次写入重置 |
| `price:`   | Agent Result Cache | Domain API 郊区中位价           | 固定过期，24 小时            |

```
session:{session_id}                    → JSON (ConversationStateDTO，snake_case 内部格式)
price:{suburb}:{property_type}:{beds}   → JSON {"median_price": 850000}
```

> `user:{user_id}:sessions`（历史列表 ZSET）属于 P1-B，`routing:{session_id}` 属于 P2，P1-A 均不实现。P1-A 中 `ChatResponse.routing` 继续内嵌返回（供前端判断触发条件）；`UserNeeds` 同时写入 PostgreSQL `sessions.final_needs`，Part 2 直接查库，无需前端转发数据（见 §16.2）。

### 21.3 P1 系统流程

```
POST /chat  {session_id, message}
       │
       ├─ 1. Redis GET session:{session_id}
       ├─ 2. Build dynamic system prompt
       ├─ 3. Call OpenRouter
       ├─ 4. Parse tool_call, merge fields
       ├─ 5. Update completionStatus
       ├─ 6. Evaluate intent routing
       ├─ 7. Redis SET session:{session_id} (KEEPTTL)
       └─ 8. Return ChatResponse
```

### 21.3.1 新 Session 自动创建

`/chat` 的第 1 步 Redis GET 返回 `None`（key 不存在或 TTL 已过期）时，**自动使用请求中的 `session_id` 创建新的 `ConversationStateDTO`**，不返回 404，不需要额外的 `POST /session` 初始化端点。

**原因：** 与 P0 行为一致（前端 P0 自己初始化 state）；前端只需生成 UUID v4 直接发送第一条消息；`session_id` 由前端生成，唯一性已有保证。

```python
# routers/chat.py（伪代码）
state: ConversationStateDTO | None = await redis_client.load_session_async(request.session_id)
if state is None:
    state = ConversationStateDTO(session_id=request.session_id)
    # 首次写入 Redis，设置完整 TTL
```

---

### 21.4 P1 接口变更

```python
# P1 ChatRequest（移除 state 字段）
class ChatRequest(BaseModel):
    session_id: str
    message:    str

# P1 ChatResponse（移除 updated_state）
class ChatResponse(BaseModel):
    reply:    str
    extracted: dict
    routing:  Optional[RoutingPayload] = None
```

### 21.5 新增端点

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/session/{session_id}` | 从 Redis 恢复完整会话状态（换标签页 / 换设备场景） |

```
→ 200: SuccessResponse<ConversationStateDTO>   （Redis 中存在）
→ 404: ErrorResponse SessionNotFoundError       （不存在或 TTL 已过期）
```

```python
# routers/session.py
@router.get("/session/{session_id}")
async def get_session_async(
    session_id: str,
    session_store: ISessionStore = Depends(get_session_store),
) -> SuccessResponse[ConversationStateDTO]:
    state: ConversationStateDTO | None = await session_store.load_state_async(session_id)
    if state is None:
        raise SessionNotFoundError(f"Session {session_id!r} not found or expired.")
    return SuccessResponse(data=state)
```

> **为何 P1 不实现 `DELETE /session`：** 前端"清除对话"只需清 sessionStorage + Zustand 本地状态，Redis key 等 7 天 TTL 自然过期即可。P1 用户量小，Redis 内存压力不大，引入删除端点收益低于维护成本。如未来 Redis 内存成为瓶颈，可在 P2 补充该端点。

---

## 22. SSE Streaming Response

> P1 实现。改善用户等待体验，目标首 token < 1s。

### 22.1 方案选择

采用**混合 SSE 方案**：文字部分实时流式推送，状态更新作为最后一个 SSE event 推送。

| 方案                    | 描述                             | 复杂度 | 体验       |
| ----------------------- | -------------------------------- | ------ | ---------- |
| 完全非流式（P0）        | 后端等全部返回，一次性响应       | 低     | 等待 5–10s |
| 后端拼装后流式          | 拼完 tool_call 再转发文字流      | 中     | 较好       |
| **混合 SSE（P1 选择）** | 文字实时推送，状态作为末尾 event | 中     | 最好       |

### 22.2 SSE Event 格式

```
event: token
data: {"text": "好的，"}

event: token
data: {"text": "请问您考虑几房的房子？"}

event: done
data: {"extracted": {...}, "routing": null}
```

### 22.3 核心约束

- `tool_call` JSON 分块传输，必须在后端拼完后再解析，不能在流中途推送状态
- 前端需同时处理 `token` event（渲染文字）和 `done` event（更新状态）
- OpenRouter 流式响应中 tool_call 的拼装逻辑需在 `llm_client.py` 中实现

---

## 23. P1-B Scope — User Accounts（规划中）

> P1-A **不实现**用户认证。P1-B 功能规划见 §20.3；设计文档待另立，本节不展开。

---

## 24. PostgreSQL Progressive Snapshot

> P1 实现。每个模块完成时异步写入 PostgreSQL，防止 Redis TTL 过期（7 天）导致进行中对话的结构化数据永久丢失。

### 24.1 设计动机

仅在 `REQUIREMENTS_COMPLETE`（M4 完成）时写库存在三个问题：

1. 用户填到 M2 就放弃 → 无任何数据留存，无法用于模块完成率统计（PRD §11 Success Metrics）
2. 对话跨越 7 天 → Redis TTL 过期后无法从 PostgreSQL 恢复，`GET /session` 返回 404
3. 无法对 M1–M3 阶段的流失做归因分析

**方案：每模块完成时累计 upsert 一次，同一 `session_id` 覆盖更新，不产生多行。**

| 触发时机 | 写入内容 |
|---------|---------|
| M1 完成 | 含 m1 的 `CollectedData` 快照，写入 `initial_intent` |
| M2 完成 | 含 m1 + m2 的 `CollectedData` 快照 |
| M3 完成 | 含 m1 + m2 + m3 的 `CollectedData` 快照 |
| M4 完成 | 含所有模块的完整 `UserNeeds`（写入 `final_needs`、`borrowing_capacity`、`completed_at`） |

### 24.2 File

```
backend/db/session_archive.py
```

### 24.3 触发机制

在 `routers/chat.py` 中，`state_machine.py` 检测到某模块从 `False → True` 后，使用 FastAPI `BackgroundTasks` 异步触发，不阻塞主请求响应：

```python
# routers/chat.py
async def chat_async(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    session_store: ISessionStore = Depends(get_session_store),
    archive: ISessionArchive = Depends(get_session_archive),
) -> ChatResponse:
    ...
    prev_completion: CompletionStatus = state.completion_status.model_copy()
    updated_state: ConversationStateDTO = merge_extracted_fields(state, extracted)

    newly_completed: bool = any(
        getattr(updated_state.completion_status, m) and not getattr(prev_completion, m)
        for m in ("M1", "M2", "M3", "M4")
    )
    if newly_completed:
        background_tasks.add_task(archive.upsert_session_snapshot_async, updated_state)
    ...
```

> **为何用 `BackgroundTasks` 而非 `asyncio.create_task`：** `BackgroundTasks` 由 FastAPI 生命周期托管，服务器关闭时不会丢失任务；`asyncio.create_task` 在进程退出时可能静默丢失写入。

### 24.4 存储范围

**写入 PostgreSQL：**

| 字段 | 说明 |
|------|------|
| `collected_data` | M1–M4 所有已收集字段，每次 upsert 累计叠加 |
| `status` | `IN_PROGRESS` / `REQUIREMENTS_COMPLETE` |
| `initial_intent` | M1 完成后首次写入 |
| `final_needs` | M4 完成后写入完整 `UserNeeds` |
| `borrowing_capacity` | M4 完成后写入借贷能力估算 |
| `completed_at` | M4 完成时写入当前时间戳 |

**不写入 PostgreSQL：**

| 内容 | 原因 |
|------|------|
| `conversation_history` | 体积大且增长不可控；PG 归档目的是结构化业务数据，不是原始聊天记录。如需完整历史，应单独建 `conversation_messages` 表 |
| `budget_gap` | 派生值——`budget_max` 在 `collected_data` 中，中位价每天更新，PG 快照次日即过时；Part 2 可按需重算 |

### 24.5 Upsert SQL

```sql
INSERT INTO sessions (
    session_id, status, schema_version, initial_intent,
    collected_data, final_needs, borrowing_capacity,
    updated_at, completed_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7, now(), $8)
ON CONFLICT (session_id)
DO UPDATE SET
    status             = EXCLUDED.status,
    initial_intent     = COALESCE(EXCLUDED.initial_intent, sessions.initial_intent),
    collected_data     = EXCLUDED.collected_data,
    final_needs        = EXCLUDED.final_needs,
    borrowing_capacity = EXCLUDED.borrowing_capacity,
    updated_at         = now(),
    completed_at       = COALESCE(EXCLUDED.completed_at, sessions.completed_at);
```

> `COALESCE` 确保 `initial_intent` 和 `completed_at` 一旦写入就不会被后续 upsert 覆盖为 null。

### 24.6 Acceptance Criteria

| ID | Criterion |
|----|-----------|
| PG-1 | M1 模块完成时，`sessions` 表中存在对应行，`collected_data` 含 m1 字段，`initial_intent` 非空 |
| PG-2 | M2 完成后 upsert，`collected_data` 包含 m1 + m2 数据，行数不变（仍为 1 行） |
| PG-3 | M4 完成后，`final_needs` 非 null，`status` 为 `REQUIREMENTS_COMPLETE`，`completed_at` 非 null |
| PG-4 | 写入异步执行（`BackgroundTasks`），不阻塞 `/chat` 端点响应时间 |
| PG-5 | `conversation_history` 和 `budget_gap` 不出现在 `sessions` 表中 |
| PG-6 | 数据库不可用时，`BackgroundTasks` 内部异常不影响主请求正常返回 `ChatResponse` |
| PG-7 | 同一 `session_id` 多次 upsert 保持幂等，`initial_intent` 和 `completed_at` 不被后续 upsert 覆盖为 null |

### 24.7 Integration Tests

```
tests/test_session_archive.py

test_upsert_on_m1_completion_writes_initial_intent
test_upsert_on_m2_completion_accumulates_m1_data
test_upsert_on_m4_completion_writes_final_needs_and_completed_at
test_upsert_is_idempotent_for_same_session_id
test_initial_intent_not_overwritten_on_subsequent_upsert
test_conversation_history_not_written_to_db
test_background_task_does_not_block_chat_response
test_db_unavailable_does_not_raise_in_main_request
```

---

## 25. Budget Gap Price Cache

> P1 实现。对 §11 S-H Budget Gap Detection 中的 Domain API 调用结果进行 Redis 缓存，避免同一地区每次对话重复调用。

### 25.1 设计动机

`budget_gap_detector.py` 调用 Domain API 查询 `suburb + property_type + min_bedrooms` 组合的中位价。同一组合在一天内结果不变，但每次对话到达 M4 时都会触发调用。P1 接入 Redis 后，顺带实现此缓存，无需额外基础设施。

此缓存属于 §21.2 定义的 **Agent Result Cache** 类型：Redis 缺失时直接穿透到 Domain API，不影响主流程正确性。

### 25.2 Redis Key Schema

```
Key:   price:{suburb}:{property_type}:{min_bedrooms}
Value: {"median_price": 850000}
TTL:   86400 秒（24 小时，固定过期，不滑动）
```

> Value 使用 JSON 对象而非裸 int，为 Part 2 将来在同一 key 里追加字段（如趋势、置信区间）预留扩展空间——当前只读 `median_price` 字段，不受影响。

### 25.3 缓存行为

```python
async def get_median_price_async(
    suburb: str,
    property_type: str,
    min_bedrooms: int,
    redis: Redis,
) -> int | None:
    key: str = f"price:{suburb.lower().replace(' ', '_')}:{property_type}:{min_bedrooms}"

    cached: str | None = await redis.get(key)
    if cached is not None:
        return json.loads(cached)["median_price"]   # cache hit — Domain API 不调用

    try:
        median_price: int = await _call_domain_api_async(suburb, property_type, min_bedrooms)
        await redis.setex(key, 86400, json.dumps({"median_price": median_price}))
        return median_price
    except Exception:
        return None   # Domain API 失败 — 不写缓存，主流程降级处理
```

### 25.4 Acceptance Criteria

| ID | Criterion |
|----|-----------|
| PC-1 | 相同 suburb / type / beds 第二次请求命中缓存，不触发 Domain API 调用 |
| PC-2 | 缓存 TTL 为 86400 秒，固定过期（不滑动） |
| PC-3 | Domain API 失败时返回 None，不写入缓存，`has_gap` 检测降级处理（返回 None，不阻断主流程） |
| PC-4 | Key 格式严格为 `price:{suburb}:{property_type}:{min_bedrooms}`，suburb 小写、空格替换为 `_` |
| PC-5 | 不同 suburb / type / beds 组合各自独立缓存，互不影响 |

### 25.5 Unit Tests

```
tests/test_budget_gap_price_cache.py

test_cache_hit_skips_domain_api_call
test_cache_miss_calls_domain_api_and_writes_cache
test_domain_api_failure_returns_none_without_writing_cache
test_cache_key_format_lowercase_suburb_with_underscore
test_different_combinations_cached_independently
test_cache_ttl_is_86400_seconds
```

---

## 26. P1 Environment Variables

> 补充 §8，列出 P1 新增的环境变量。§8 原有变量不变。

| Variable                 | Required | Default                  | Description                        |
| ------------------------ | -------- | ------------------------ | ---------------------------------- |
| `REDIS_URL`              | P1 Yes   | `redis://localhost:6379` | Redis 连接地址                     |
| `REDIS_SESSION_TTL`      | No       | `604800`                 | 会话 TTL（秒），默认 7 天          |
| `DATABASE_URL`           | P1 Yes   | —                        | PostgreSQL 连接串（asyncpg 格式）  |
| `DOMAIN_API_KEY`         | P1 Yes   | —                        | Domain API key（S-H 预算缺口检测） |
| `BUDGET_GAP_THRESHOLD`   | No       | `0.15`                   | 预算缺口触发阈值                   |
| `BORROWING_CAPACITY_DTI` | No       | `0.28`                   | DTI 上限，借款能力计算用           |
| `SESSION_SECRET_KEY`     | P1-B     | —                        | 会话签名密钥（P1-A 不需要）        |
| `LOG_LEVEL`              | No       | `INFO`                   | 日志级别                           |

---

## 27. P1 Non-Functional Requirements

> 补充主 PRD §10，列出 Part 1 专项 NFR。

| 类别   | 要求                         | 目标值                             | 测量方式        |
| ------ | ---------------------------- | ---------------------------------- | --------------- |
| 性能   | AI 首 token 延迟（流式）     | < 1s                               | CloudWatch P95  |
| 性能   | `/chat` 端点总延迟（非流式） | < 10s P95                          | CloudWatch      |
| 性能   | 会话加载（Redis GET）        | < 50ms P99                         | Redis LATENCY   |
| 可用性 | 会话数据持久性               | 7 天内可恢复                       | Redis TTL 监控  |
| 安全   | session_id 格式              | UUID v4，不可猜测                  | 单元测试        |
| 安全   | 对话历史                     | 不在日志中记录用户消息原文         | 日志审计        |
| 隐私   | 用户数据不用于训练           | OpenRouter `data-collection: deny` | 请求头审计      |
| 合规   | 守卫规则覆盖率               | 6/6 规则在系统提示中存在           | SC-7 自动化测试 |

**OpenRouter 隐私请求头（P1 起必须设置）：**

```python
headers = {
    "HTTP-Referer": "https://propertyai.com.au",
    "X-Title": "PropertyAI",
    "X-Data-Collection": "deny"
}
```

---

## 28. P1 Deployment Notes

### 28.1 Docker Compose（P1-A 新增服务配置）

```yaml
services:
  app:
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/propertyai
      - DOMAIN_API_KEY=${DOMAIN_API_KEY}
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

### 28.2 Health Check 端点（P1-A 扩展）

```python
# GET /health — P1 起检查所有依赖服务
{
    "status": "healthy" | "degraded" | "unhealthy",
    "checks": {
        "redis":      {"status": "ok", "latency_ms": 1},
        "postgres":   {"status": "ok", "latency_ms": 5},
        "openrouter": {"status": "ok"}
    },
    "version": "1.1.0"
}
```

### 28.3 P1-A Project Structure 更新

```
backend/
├── main.py
├── models/
│   └── schemas.py
├── tools/
│   └── extraction_schema.py
├── conversation/
│   ├── state_machine.py
│   └── intent_router.py
├── prompts/
│   └── system_prompt_builder.py
├── domain/
│   ├── llm_client.py
│   ├── borrowing_capacity.py       # S-G（P0新增）
│   ├── budget_gap_detector.py      # S-H（P0新增）
│   ├── user_needs_builder.py       # P0新增
│   └── redis/                      # P1新增：Redis 子包
│       ├── client.py               # 连接管理（connect/close/ping + raw get/setex）
│       ├── session_store.py        # ISessionStore Protocol + RedisSessionStore
│       └── price_cache.py          # RedisPriceCache（Domain API 中位价，24h TTL）
├── routers/
│   ├── chat.py
│   └── session.py                  # P1新增：GET /session/{session_id}（§21.5）
├── db/
│   └── session_archive.py          # P1新增：PostgreSQL 渐进快照 upsert（§24）
└── tests/
    ├── test_extraction_schema.py
    ├── test_state_machine.py
    ├── test_system_prompt.py
    ├── test_chat_endpoint.py
    ├── test_intent_router.py
    ├── test_summary.py
    ├── test_borrowing_capacity.py   # S-G（P0新增）
    ├── test_budget_gap_detector.py  # S-H（P0新增）
    ├── test_guardrail_rules.py      # P0新增
    ├── test_session_archive.py      # §24（P1新增）
    └── test_budget_gap_price_cache.py  # §25（P1新增）
```
