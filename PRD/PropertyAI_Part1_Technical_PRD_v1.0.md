# PropertyAI — Part 1 Conversation Layer
## Technical PRD v1.0

| Field | Value |
|-------|-------|
| Version | v1.1 |
| Status | Pending Confirmation |
| Parent Document | PropertyAI PRD v1.1 |
| Scope | Part 1 Conversation Layer — P0 Implementation |
| Last Updated | 8 May 2026 |

---

## Table of Contents

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
       ├─ 2. Append user message to conversationHistory
       │
       ├─ ── Round 1: Extraction ──────────────────────────────────
       ├─ 3. Build extraction system prompt (build_extraction_prompt)
       ├─ 4. Call OpenRouter with extract_requirements tool
       ├─ 5. Parse tool_call → extracted fields dict
       ├─ 6. Merge new fields into collectedData (merge_extracted_fields)
       ├─ 7. Recalculate completionStatus + advance current_module
       │
       ├─ ── Round 2: Question Generation ──────────────────────────
       ├─ 8. Build question system prompt (build_question_prompt)
       │      (sees updated state with freshly extracted fields)
       ├─ 9. Call OpenRouter plain completion → assistant reply string
       │
       ├─ 10. Append assistant reply to conversationHistory
       ├─ 11. Evaluate whether to trigger intent routing (classify_intent)
       └─ 12. Return ChatResponse (reply + extracted + updated_state + routing)

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

The tool name must be `extract_requirements`.

All fields are optional — the LLM only populates fields the user has explicitly stated. There are no required fields and no control fields (`module_complete`, `next_question`, `user_intent` have been removed). Module completion detection and reply generation are handled by separate logic in Round 2.

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
    pre_tax_salary, is_joint, partner_salary, first_home_buyer
```

#### Acceptance Criteria

| ID | Criterion |
|----|-----------|
| SA-1 | Schema can be serialised by `json.dumps()` without error |
| SA-2 | `name` field value is strictly equal to `"extract_requirements"` |
| SA-3 | The `required` list is empty (no required fields) |
| SA-4 | Control fields `module_complete`, `next_question`, and `user_intent` are absent from the schema |
| SA-5 | `property_type` enum values match PRD exactly: `["house","townhouse","unit","apartment","villa","any"]` |
| SA-6 | `commute_mode` enum values match PRD exactly: `["train","car","tram","bus","any"]` |
| SA-7 | `preferred_suburbs` and `excluded_suburbs` have type `array` with items of type `string` |

#### Unit Tests

```
tests/test_extraction_schema.py

test_schema_is_json_serialisable
test_tool_name_is_extract_requirements
test_required_list_is_empty
test_control_fields_absent_from_schema
test_property_type_enum_values
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

| Module | Required Fields | Special Rule |
|--------|----------------|--------------|
| M1 | `property_type` + `min_bedrooms` + `intended_use` | All three must be non-None |
| M2 | `household_size` + `has_children` | If `intended_use == "investment"`, also requires `target_tenant` |
| M3 | `commute_destination` + `commute_max_mins` | Both must be non-None |
| M4 | `budget_max` | Must be non-None |

**`current_module` progression rule:**

Advances in order M1 → M2 → M3 → M4. Once the current module is complete, advance to the next. When all modules are complete, `status` becomes `REQUIREMENTS_COMPLETE`.

**Non-linear jump:**

`merge_extracted_fields()` accepts fields from any module and writes them to the corresponding sub-model without restricting to the current module. After merging, `completionStatus` is immediately recalculated.

**Null protection:**

Existing non-None field values must not be overwritten by incoming None values. Only non-None new values trigger an update.

#### Acceptance Criteria

| ID | Criterion |
|----|-----------|
| SB-1 | When all M1 required fields are populated, `is_module_complete(M1, data)` returns `True` |
| SB-2 | When any M1 required field is None, returns `False` |
| SB-3 | When `intended_use == "investment"` and `target_tenant` is None, M2 returns `False` |
| SB-4 | When `intended_use == "owner_occupier"`, M2 does not require `target_tenant` |
| SB-5 | When M1 is incomplete, `get_current_module()` returns `M1_PROPERTY_NEEDS` |
| SB-6 | When M1 is complete and M2 is incomplete, returns `M2_LIFESTYLE` |
| SB-7 | When all four modules are complete, returns `COMPLETE` |
| SB-8 | When user provides M3 fields during M1 stage, `merge_extracted_fields()` correctly writes to `collectedData.m3` without error |
| SB-9 | After merge, `completionStatus` is immediately recalculated and correctly reflects each module's state |
| SB-10 | Existing non-None field values are not overwritten by incoming None values |

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

Expose three prompt-builder functions for the two-round LLM call architecture and the summary endpoint. All LLM prompt strings must live exclusively in this file.

#### File

```
backend/prompts/system_prompt_builder.py
```

#### Specification

##### `build_extraction_prompt(state)` — Round 1

A minimal prompt focused solely on field extraction. It **must not** ask the model to generate a reply or question.

Required content:
- Active module identifier (so the model knows which sub-model to focus on)
- Instruction to extract only explicitly stated fields, without inference

##### `build_question_prompt(state)` — Round 2

A full prompt for generating the next guiding question. It **must not** ask the model to perform field extraction. Assembled from the following sections in fixed order:

**Section 1 — Role Definition (static)**

```
You are an AI property buying assistant for the Australian market.
Your role is to collect buyer requirements through natural conversation.
You are NOT a licensed buyer's agent, financial advisor, or legal professional.
```

**Section 2 — Updated State Injection (dynamic)**

Reflects the state *after* Round 1 extraction:

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

```
Rule 1 — Property recommendations: present data only, never give a direct recommendation
Rule 2 — Market information: provide data, always follow with a question returning focus to user needs
Rule 3 — Budget shortfall: flag the gap directly and kindly, suggest alternatives
Rule 4 — Legal/compliance: explain concepts, refer to solicitor or conveyancer
Rule 5 — Investment predictions: historical data only, always append ASIC disclaimer
Rule 6 — Role identity: transparent explanation of AI assistant boundaries
```

**Section 5 — Question Task Instruction (static)**

```
Task: Generate exactly ONE short, natural, conversational question targeting the most
important missing required field for the current module. Do not re-ask fields already collected.
```

##### `build_system_prompt(state)` — Legacy / Summary

Retained for backward compatibility. Used by `POST /chat/summary` and any callers that pre-date the two-round refactor. Identical structure to `build_question_prompt` minus Section 5.

#### Acceptance Criteria

| ID | Criterion |
|----|-----------|
| SC-1 | `build_question_prompt` output contains role definition, state section, guardrail rules, and task instruction |
| SC-2 | `build_question_prompt` reflects the correct `current_module` |
| SC-3 | `build_question_prompt` lists non-None collected fields; None fields do not appear |
| SC-4 | When M1 is incomplete, Section 3 is absent from both `build_question_prompt` and `build_system_prompt` |
| SC-5 | When M1 complete and `intended_use == "investment"`, Section 3 contains tenant guidance |
| SC-6 | When M1 complete and `intended_use == "owner_occupier"`, Section 3 contains school zone guidance |
| SC-7 | All six guardrail rules appear in `build_question_prompt` output |
| SC-8 | `build_extraction_prompt` output does not contain question-generation instruction |
| SC-9 | `build_extraction_prompt` output contains the active module identifier |
| SC-10 | All three functions return non-empty strings without raising |

#### Unit Tests

```
tests/test_system_prompt.py

# build_system_prompt (existing)
test_output_contains_role_definition
test_output_contains_current_module
test_collected_summary_excludes_none_fields
test_section_3_absent_when_m1_incomplete
test_section_3_contains_tenant_guidance_for_investment
test_section_3_contains_school_guidance_for_owner_occupier
test_all_six_guardrail_rules_present
test_output_is_nonempty_string

# build_extraction_prompt (new)
test_extraction_prompt_contains_active_module
test_extraction_prompt_excludes_question_instruction

# build_question_prompt (new)
test_question_prompt_contains_role_definition
test_question_prompt_contains_missing_fields
test_question_prompt_contains_task_instruction
test_question_prompt_guardrail_rules_present
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
    reply:         str                         # assistant reply from Round 2
    extracted:     dict                        # business fields extracted in Round 1
    updated_state: ConversationStateDTO
    routing:       Optional[RoutingPayload] = None
```

**Endpoint processing sequence (fixed order):**

1. Load current state from `request.state`
2. Append user message to `conversationHistory`
3. **Round 1 — Extraction**
   - Call `build_extraction_prompt(state)` → extraction-focused system prompt
   - Call `llm_client.chat_with_tools_async()` with `EXTRACT_REQUIREMENTS_TOOL`
   - Returns `extracted: dict[str, object]` (business fields only, no control keys)
4. Call `merge_extracted_fields(state, extracted)` — merges fields, advances module, recalculates completion
5. **Round 2 — Question Generation**
   - Call `build_question_prompt(updated_state)` → question-focused system prompt (sees freshly updated state)
   - Call `llm_client.complete_async(question_prompt, request.message)` → `reply: str`
6. Append `reply` to `conversationHistory`
7. Call `classify_intent(request.message, state)` to determine routing
8. Return `ChatResponse`

**LLM client method signatures:**

```python
# Round 1
async def chat_with_tools_async(
    system_prompt: str,
    messages: list[dict[str, object]],
    tools: list[dict[str, object]],
) -> dict[str, object]:  # extracted business fields only
    ...

# Round 2
async def complete_async(
    system_prompt: str,
    user_message: str,
) -> str:  # assistant reply
    ...
```

**LLM call configuration (both rounds):**

| Parameter | Value |
|-----------|-------|
| Model | `MODEL_STRONG` (`anthropic/claude-sonnet-4-5`, overridable via env var) |
| Temperature | 0.7 |
| Max tokens | 1000 |
| Round 1 tool choice | `"auto"` |

**Error handling:**

| Scenario | Response |
|----------|----------|
| `message` is empty string | HTTP 422 |
| OpenRouter call fails (either round) | HTTP 503 with error envelope |
| Round 1 LLM returns no tool_call | `extracted: {}`, Round 2 still executes |

#### Acceptance Criteria

| ID | Criterion |
|----|-----------|
| SD-1 | Valid request returns HTTP 200 with response conforming to `ChatResponse` schema |
| SD-2 | `updated_state.conversationHistory` contains both the user message and the Round 2 assistant reply |
| SD-3 | `extracted` contains only business fields from Round 1; is `{}` when the LLM returns no tool_call |
| SD-4 | `updated_state.collectedData` reflects fields extracted in Round 1 |
| SD-5 | `updated_state.completionStatus` is recalculated after Round 1 before Round 2 is called |
| SD-6 | When Round 1 LLM returns no tool_call, `extracted` is `{}` and Round 2 still executes without error |
| SD-7 | When `message` is an empty string, returns HTTP 422 |
| SD-8 | When OpenRouter call fails, returns HTTP 503 with error envelope |
| SD-9 | Across multiple turns, `conversationHistory` accumulates correctly and is not reset |

#### Integration Tests

Each test must mock **both** `chat_with_tools_async` (returns `dict`) **and** `complete_async` (returns `str`).

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

| Intent | Trigger Condition |
|--------|------------------|
| `recommend_suburbs` | Contains "suburb", "area", "recommend", "推荐", "区域" |
| `list_properties` | Contains "property", "listing", "find", "找房", "房源" |
| `property_detail` | Message contains a specific address or property_id |
| `open_ended_query` | All other cases where `all_complete` is True |

**`RoutingPayload` definition:**

```python
@dataclass
class RoutingPayload:
    intent:         str   # one of the five intents above
    collected_data: CollectedData
    session_id:     str
```

#### Acceptance Criteria

| ID | Criterion |
|----|-----------|
| SE-1 | When `all_complete == False` and message contains no trigger keywords, returns `None` |
| SE-2 | When `all_complete == True`, returns a non-None `RoutingPayload` |
| SE-3 | When message contains "recommend", `intent == "recommend_suburbs"` |
| SE-4 | When message contains a specific address, `intent == "property_detail"` |
| SE-5 | When `all_complete == True` and no explicit intent is detected, `intent == "open_ended_query"` |
| SE-6 | `RoutingPayload.collected_data` equals the current `collectedData` |
| SE-7 | `RoutingPayload.session_id` equals the current `sessionId` |

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

| ID | Criterion |
|----|-----------|
| SF-1 | Valid request returns HTTP 200 with `summary_text` as a non-empty string |
| SF-2 | `summary_text` contains the value of `budget_max` (if non-None) |
| SF-3 | `summary_text` contains the value of `property_type` (if non-None) |
| SF-4 | `summary_text` contains the value of `commute_destination` (if non-None) |
| SF-5 | `structured` field equals the input `collected_data` without modification |
| SF-6 | When all fields are None, returns HTTP 422 |

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

All stories share the following models. They are split across three files by domain:

| File | Models |
|------|--------|
| `models/conversation_state.py` | Enums, M1–M4 sub-models, `CollectedData`, `CompletionStatus`, `ConversationStateDTO` |
| `models/chat.py` | `ChatRequest`, `ChatResponse`, `RoutingPayload` |
| `models/summary.py` | `SummaryRequest`, `SummaryResponse` |

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

```sql
CREATE TABLE users (
    user_id     UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE,
    browser_fp  VARCHAR(255),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
    session_id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID         REFERENCES users(user_id),
    status               VARCHAR(50)  NOT NULL DEFAULT 'IN_PROGRESS',
    current_module       VARCHAR(50)  NOT NULL DEFAULT 'M1_PROPERTY_NEEDS',
    completion_status    JSONB        NOT NULL DEFAULT '{}',
    collected_data       JSONB        NOT NULL DEFAULT '{}',
    conversation_history JSONB        NOT NULL DEFAULT '[]',
    final_needs          JSONB,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_active_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    completed_at         TIMESTAMPTZ
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
```

---

## 6. Project Structure

```
backend/
├── main.py
├── models/
│   ├── conversation_state.py         # Enums, M1–M4 sub-models, CollectedData,
│   │                                 # CompletionStatus, ConversationStateDTO
│   ├── chat.py                       # ChatRequest, ChatResponse, RoutingPayload
│   └── summary.py                    # SummaryRequest, SummaryResponse
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

Cover S-D and S-F using `pytest` + `httpx.AsyncClient` + `unittest.mock`. Each test must mock **both** `chat_with_tools_async` (Round 1, returns `dict`) and `complete_async` (Round 2, returns `str`).

```python
# Example: S-D integration test
@pytest.mark.asyncio
async def test_chat_endpoint_returns_updated_state():
    tools_mock = AsyncMock(return_value={
        "property_type": "house",
        "min_bedrooms": 3,
        "intended_use": "owner_occupier",
    })
    complete_mock = AsyncMock(return_value="Great, tell me about your lifestyle.")
    with (
        patch.object(chat_module._default_llm_client, "chat_with_tools_async", tools_mock),
        patch.object(chat_module._default_llm_client, "complete_async", complete_mock),
    ):
        response = await client.post("/api/v1/chat", json={...})
    assert response.status_code == 200
    data = response.json()
    assert data["updatedState"]["collectedData"]["m1"]["propertyType"] == "house"
    assert data["reply"] == "Great, tell me about your lifestyle."
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

| Layer | Target Coverage |
|-------|----------------|
| `models/schemas.py` | 100% |
| `tools/extraction_schema.py` | 100% |
| `conversation/state_machine.py` | 100% |
| `conversation/intent_router.py` | 100% |
| `prompts/system_prompt_builder.py` | 100% |
| `routers/chat.py` | ≥ 80% |
| `services/llm_client.py` | ≥ 80% |

---

## 8. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes | — | OpenRouter API key |
| `MODEL_STRONG` | No | `anthropic/claude-sonnet-4-5` | Model for conversation turns |
| `MODEL_FAST` | No | `anthropic/claude-haiku-4-5` | Model for lightweight extraction |

---

## 9. E2E Acceptance Criteria

The P0 implementation is considered complete when all of the following are satisfied:

| ID | Criterion |
|----|-----------|
| E2E-1 | After completing the four-module conversation, `status == "REQUIREMENTS_COMPLETE"` |
| E2E-2 | `collectedData` contains all required fields from all four modules with correct values |
| E2E-3 | Budget information volunteered by the user during M1 stage is correctly saved to `collectedData.m4` |
| E2E-4 | `POST /chat/summary` returns a summary covering budget, property type, commute, and lifestyle |
| E2E-5 | `ChatResponse.routing` is non-None after `all_complete` is triggered |
| E2E-6 | All unit tests pass (0 failures) |
| E2E-7 | All integration tests pass (0 failures) |
