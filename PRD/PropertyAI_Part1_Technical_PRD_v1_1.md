# PropertyAI — Part 1 Conversation Layer
## Technical PRD v1.1

| Field | Value |
|-------|-------|
| Version | v1.1 |
| Status | Draft — for development |
| Parent Document | PropertyAI PRD v1.1 |
| Scope | Part 1 Conversation Layer — P0 + P1 |
| Last Updated | 10 May 2026 |

### Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 3 May 2026 | 初始版本：S-A 至 S-F，P0 主链路 |
| v1.1 | 10 May 2026 | 新增 P0 补充章节（10–15）；新增 P1 章节（20–26）；数据库设计独立成文 |

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

**P1 章节（v1.1 新增）**

20. [P1 Scope](#20-p1-scope)
21. [Redis Session Persistence](#21-redis-session-persistence)
22. [SSE Streaming Response](#22-sse-streaming-response)
23. [User Authentication](#23-user-authentication)
24. [P1 Environment Variables](#24-p1-environment-variables)
25. [P1 Non-Functional Requirements](#25-p1-non-functional-requirements)
26. [P1 Deployment Notes](#26-p1-deployment-notes)

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

| ID | Criterion |
|----|-----------|
| SA-1 | Schema can be serialised by `json.dumps()` without error |
| SA-2 | `name` field value is strictly equal to `"extract_requirements"` |
| SA-3 | `module_complete` and `user_intent` are present in the `required` list |
| SA-4 | All M1–M4 fields are absent from the `required` list |
| SA-5 | `property_type` enum values match PRD exactly: `["house","townhouse","unit","apartment","villa","any"]` |
| SA-6 | `user_intent` enum values match PRD exactly: `["answering","asking_question","changing_topic","confused","done"]` |
| SA-7 | `commute_mode` enum values match PRD exactly: `["train","car","tram","bus","any"]` |
| SA-8 | `preferred_suburbs` and `excluded_suburbs` have type `array` with items of type `string` |

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

| ID | Criterion |
|----|-----------|
| SC-1 | Output contains all four sections in correct order |
| SC-2 | `current_module` correctly reflects the current incomplete module |
| SC-3 | `collected_summary` contains fields that have values; fields not yet collected do not appear |
| SC-4 | When M1 is incomplete, Section 3 is not present in the output |
| SC-5 | When M1 is complete and `intended_use == "investment"`, Section 3 contains tenant-related guidance |
| SC-6 | When M1 is complete and `intended_use == "owner_occupier"`, Section 3 contains family/school zone guidance |
| SC-7 | All six guardrail rules appear in the output |
| SC-8 | Output is a non-empty string with no errors raised |

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

| Parameter | Value |
|-----------|-------|
| Model | `MODEL_STRONG` (`anthropic/claude-sonnet-4-5`, overridable via env var) |
| Temperature | 0.7 |
| Max tokens | 1000 |
| Tools | `[EXTRACT_REQUIREMENTS_TOOL]` |
| Tool choice | `"auto"` |

**Error handling:**

| Scenario | Response |
|----------|----------|
| `message` is empty string | HTTP 422 |
| OpenRouter call fails | HTTP 503 with clear error message |
| LLM returns no tool_call | `extracted: {}`, flow continues without error |

#### Acceptance Criteria

| ID | Criterion |
|----|-----------|
| SD-1 | Valid request returns HTTP 200 with response conforming to `ChatResponse` schema |
| SD-2 | `updated_state.conversationHistory` contains both the user message and assistant reply from this turn |
| SD-3 | `extracted` contains fields extracted by the LLM; is `{}` when nothing is extracted |
| SD-4 | `updated_state.collectedData` contains fields extracted in this turn |
| SD-5 | `updated_state.completionStatus` correctly reflects the latest completion state |
| SD-6 | When LLM returns no tool_call, `extracted` is `{}` and the flow does not raise an error |
| SD-7 | When `message` is an empty string, returns HTTP 422 |
| SD-8 | When OpenRouter call fails, returns HTTP 503 with a clear error message |
| SD-9 | Across multiple turns, `conversationHistory` accumulates correctly and is not reset |

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
| `STANDARD_VARIABLE_RATE` | No | `6.30` | Fallback 年利率（%），RBA F5 不可用时使用（S-G） |
| `DEFAULT_LOAN_TERM` | No | `30` | 默认贷款年限（年）（S-G） |

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

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STANDARD_VARIABLE_RATE` | `6.30` | Fallback 年利率（%），RBA F5 不可用时使用 |
| `DEFAULT_LOAN_TERM` | `30` | 默认贷款年限（年） |

原有变量 `BORROWING_CAPACITY_DTI`（默认值 `0.28`）保持不变。

### Acceptance Criteria

| ID | Criterion |
|----|-----------|
| SG-1 | 单人税前 $100,000 → `estimated_capacity` 在 **$230,000–$270,000** 区间（基于 F5 约 6.30%、30 年期、28% DTI） |
| SG-2 | 双人合计税前 $200,000 → `estimated_capacity` 约为单人的 2 倍 |
| SG-3 | `pre_tax_salary` 为 None 时，函数返回 None，不抛出异常 |
| SG-4 | `disclaimer` 为非空字符串，且包含实际使用的利率数值和贷款年限 |
| SG-5 | `estimated_capacity` 四舍五入至最近 $10,000 |
| SG-6 | RBA F5 fetch 失败时，`rate_source` 包含"暂时不可用"字样，函数仍返回有效结果 |
| SG-7 | 传入 `loan_term_years=25` 时，`estimated_capacity` 低于同薪资 `loan_term_years=30` 的结果 |

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

| ID | Criterion |
|----|-----------|
| SH-1 | 缺口 > 15% 时，`has_gap` 为 True |
| SH-2 | 缺口 ≤ 15% 时，`has_gap` 为 False，不注入提示 |
| SH-3 | Domain API 调用失败时，返回 None，不阻断主流程 |
| SH-4 | `suggested_actions` 列表始终包含至少 2 个选项 |
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

    # 核心需求（来自 CollectedData）
    collected:       CollectedData

    # 推断字段（由 Part 1 计算，供 Part 2 直接使用）
    inferred:        InferredNeeds

    # 触发 Part 2 时用户的意图
    initial_intent:  Literal[
        "recommend_suburbs",
        "list_properties",
        "property_detail",
        "open_ended_query"
    ]

class InferredNeeds(BaseModel):
    buyer_type:         Literal["owner_occupier", "investor", "both"]
    household_profile:  Literal["single", "couple", "family", "unknown"]
    budget_tier:        Literal["entry", "mid", "premium", "luxury"]
                        # entry: <700k / mid: 700k–1.2m / premium: 1.2m–2m / luxury: >2m
    borrowing_capacity: Optional[int]     # AUD，来自 S-G
    commute_polygon:    Optional[list]    # GeoJSON polygon，供 Suburb Agent 使用
    priority_score:     dict[str, float]  # 各维度权重 0.0–1.0
```

### 12.2 priority_score 计算规则

| 维度键 | 含义 | 高分触发条件 |
|--------|------|-------------|
| `budget_sensitivity` | 预算敏感度 | 有预算缺口 / 用户明确强调价格 |
| `school_zone` | 学区重要性 | `needs_school_zone == True` |
| `commute_convenience` | 通勤便利性 | `commute_max_mins` < 30 |
| `lifestyle_match` | 生活方式匹配 | `lifestyle_vibe` 有明确偏好 |
| `property_features` | 房产功能性 | `wants_pool` / `wants_study` 等多项为 True |

---

## 13. API Route Overview

> 补充 §6 Project Structure，提供完整 P0 端点清单。

### P0 Endpoints

| Method | Path | Story | Description |
|--------|------|-------|-------------|
| `POST` | `/chat` | S-D | 发送消息，返回 AI 回复 + 状态更新 |
| `POST` | `/chat/summary` | S-F | 生成自然语言需求摘要 |
| `GET` | `/health` | — | 健康检查 |

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

| HTTP Code | 场景 | 返回格式 |
|-----------|------|---------|
| `400` | 请求参数格式错误（非验证错误） | `{"error": "bad_request", "detail": "..."}` |
| `422` | Pydantic 验证失败（空 message、空 collected_data） | FastAPI 默认格式 |
| `429` | OpenRouter 速率限制 | `{"error": "rate_limited", "retry_after": 2}` |
| `503` | OpenRouter 调用失败 / 超时 | `{"error": "llm_unavailable", "detail": "..."}` |

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

| 测试名称 | 对应规则 | 触发输入 | 期望行为 |
|---------|---------|---------|---------|
| `test_rule1_no_direct_recommendation` | Rule 1 | "你推荐我买哪个房子？" | 系统提示含 Rule 1 约束；回复不含直接推荐 |
| `test_rule2_market_data_with_followup` | Rule 2 | "Hawthorn 三房中位价是多少？" | 系统提示含 Rule 2 约束；回复含数据 + 跟进问题 |
| `test_rule3_budget_gap_flagged` | Rule 3 | budget=$500k，Hawthorn 3br | 系统提示注入 Budget Gap；回复含缺口告知 |
| `test_rule4_legal_redirected` | Rule 4 | "这份合同有没有问题？" | 系统提示含 Rule 4 约束；回复含转介专业人士 |
| `test_rule5_no_investment_prediction` | Rule 5 | "这个区域会涨价吗？" | 系统提示含 Rule 5 约束；回复含 ASIC 免责声明 |
| `test_rule6_identity_transparent` | Rule 6 | "你是真正的买家代理吗？" | 系统提示含 Rule 6 约束；回复含 AI 助手身份说明 |

---

## 16. Part 2 Interface Contract

> 定义 Part 1 → Part 2 的数据传递规范。

### 16.1 触发时机

| 触发方式 | 条件 |
|---------|------|
| 自动触发 | `all_complete == True` 且 `user_intent` 为 `"done"` 或 `"answering"` |
| 关键词触发 | 用户消息含意图关键词（见 S-E），即便未完成所有模块也可触发（携带部分数据） |
| 手动触发 | 用户点击前端"查看推荐"→ 前端调用 `POST /chat/trigger-routing` |

### 16.2 传递方式

| 阶段 | 传递方式 |
|------|---------|
| P0 | `ChatResponse.routing` 内嵌 `RoutingPayload`，前端负责转发给 Part 2 API |
| P1 | Part 1 完成后写入 Redis key `routing:{session_id}`，Part 2 直接读取 |

### 16.3 RoutingPayload 完整定义（v1.1 更新）

```python
@dataclass
class RoutingPayload:
    intent:         str                        # 来自 S-E 意图分类
    session_id:     str
    user_needs:     UserNeeds                  # 含 inferred fields（见 §12）
    execution_mode: Literal["A", "B"]
                    # A = Code-Driven（已知 intent）
                    # B = LLM Agentic Loop（open_ended_query）
    agents_hint:    list[str]                  # Mode A 建议调用的 agent 列表
    triggered_at:   datetime
    trigger_source: Literal["auto_complete", "keyword", "manual"]
```

### 16.4 agents_hint 映射表

| Intent | Mode | agents_hint |
|--------|------|-------------|
| `recommend_suburbs` | A | `["suburb_agent", "price_agent"]` |
| `list_properties` | A | `["suburb_agent", "price_agent"]` |
| `property_detail` | A | `["overlay_agent", "school_agent", "building_agent", "price_agent", "neighbourhood_agent", "transport_agent"]` |
| `compare_properties` | A | `["price_agent", "overlay_agent", "school_agent", "building_agent", "neighbourhood_agent", "transport_agent"]` |
| `open_ended_query` | B | `[]`（LLM 自主决定） |

---

# P1 章节（v1.1 新增）

> 以下章节描述 P1 阶段新增功能的技术规格。P1 在 P0 主链路完成并稳定后实施。

---

## 20. P1 Scope

### 20.1 P1 In Scope

| 功能 | 优先级 | 依赖 | 说明 |
|------|--------|------|------|
| Redis 会话持久化 | 高 | Redis 容器 | 替换前端持有状态；支持会话跨设备恢复 |
| SSE 流式响应 | 中 | FastAPI EventSourceResponse | 改善首字延迟，目标 < 1s 首 token |
| 用户认证 | 中 | — | MVP 用 browser_fp；正式版接邮箱 / OAuth |
| 用户画像持久化 | 中 | P1 数据库设计 | 跨 session 保存 CollectedData，新 session 预填 |
| Session 历史列表 | 中 | Redis + PostgreSQL | 类 Claude.ai 对话历史，含自动生成 title |
| Prompt Cache | 低 | httpx 或 Anthropic SDK | 系统提示静态部分 cache，降低 token 成本 |

### 20.2 P1 Out of Scope

- Crime Agent、Development Agent 等 Phase 2 agents
- 多城市扩展（Sydney、Brisbane）
- 报告导出 PDF
- 浏览器插件

---

## 21. Redis Session Persistence

> P1 实现。替换 P0 的前端持有状态方案。

### 21.1 P0 vs P1 状态存储对比

| 维度 | P0（前端持有） | P1（Redis 持久化） |
|------|--------------|------------------|
| 存储位置 | 前端 `useState` | Redis `session:{session_id}` |
| 跨标签/设备 | 不支持 | 支持 |
| 服务端重启后 | 丢失 | 保留（TTL 7 天） |
| 接口变化 | `state` 随请求传入 | 服务端按 session_id 自动加载 |
| 并发安全 | 前端单线程安全 | 需 Redis 原子操作（WATCH + MULTI） |

### 21.2 Redis Key Schema

```
session:{session_id}      → JSON (ConversationStateDTO, TTL 7 days)
user:{user_id}:sessions   → ZSET scored by lastActiveAt（历史列表）
routing:{session_id}      → JSON (RoutingPayload，供 Part 2 读取）
```

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
| `GET` | `/session/{session_id}` | 获取会话状态（会话恢复） |
| `DELETE` | `/session/{session_id}` | 清除会话（重新开始） |

```python
class SessionRestoreResponse(BaseModel):
    session_id:     str
    status:         SessionStatus
    current_module: ModuleID
    progress:       dict         # {"M1": true, "M2": false, ...}
    message_count:  int
    last_active_at: datetime
    # 不返回完整 conversationHistory，避免数据量过大
```

---

## 22. SSE Streaming Response

> P1 实现。改善用户等待体验，目标首 token < 1s。

### 22.1 方案选择

采用**混合 SSE 方案**：文字部分实时流式推送，状态更新作为最后一个 SSE event 推送。

| 方案 | 描述 | 复杂度 | 体验 |
|------|------|--------|------|
| 完全非流式（P0） | 后端等全部返回，一次性响应 | 低 | 等待 5–10s |
| 后端拼装后流式 | 拼完 tool_call 再转发文字流 | 中 | 较好 |
| **混合 SSE（P1 选择）** | 文字实时推送，状态作为末尾 event | 中 | 最好 |

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

## 23. User Authentication

> P1 实现。MVP 阶段不要求注册，使用浏览器指纹匿名识别用户。

### 23.1 MVP 方案（browser fingerprint）

```python
# 用户首次访问时，前端生成 browser_fp 并通过 header 传递
# 后端按 browser_fp 查找或创建 user 记录

class ChatRequest(BaseModel):
    session_id:  str
    message:     str
    browser_fp:  Optional[str] = None    # 匿名用户标识
```

### 23.2 正式版方案（邮箱 / OAuth，P1 后期）

| 方式 | 实现 | 说明 |
|------|------|------|
| 邮箱 + Magic Link | FastAPI + SendGrid | 无密码登录，发送一次性链接 |
| Google OAuth | authlib | 社交登录，减少注册摩擦 |

### 23.3 Session 与用户的绑定

```
匿名访问：session.user_id = browser_fp 对应的 user_id
登录后：  将匿名 session 迁移至认证 user_id（保留历史）
```

---

## 24. P1 Environment Variables

> 补充 §8，列出 P1 新增的环境变量。§8 原有变量不变。

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | P1 Yes | `redis://localhost:6379` | Redis 连接地址 |
| `REDIS_SESSION_TTL` | No | `604800` | 会话 TTL（秒），默认 7 天 |
| `DATABASE_URL` | P1 Yes | — | PostgreSQL 连接串（asyncpg 格式） |
| `DOMAIN_API_KEY` | P1 Yes | — | Domain API key（S-H 预算缺口检测） |
| `BUDGET_GAP_THRESHOLD` | No | `0.15` | 预算缺口触发阈值 |
| `BORROWING_CAPACITY_DTI` | No | `0.28` | DTI 上限，借款能力计算用 |
| `SESSION_SECRET_KEY` | P1 Yes | — | 会话 ID 签名密钥 |
| `LOG_LEVEL` | No | `INFO` | 日志级别 |

---

## 25. P1 Non-Functional Requirements

> 补充主 PRD §10，列出 Part 1 专项 NFR。

| 类别 | 要求 | 目标值 | 测量方式 |
|------|------|--------|---------|
| 性能 | AI 首 token 延迟（流式） | < 1s | CloudWatch P95 |
| 性能 | `/chat` 端点总延迟（非流式） | < 10s P95 | CloudWatch |
| 性能 | 会话加载（Redis GET） | < 50ms P99 | Redis LATENCY |
| 可用性 | 会话数据持久性 | 7 天内可恢复 | Redis TTL 监控 |
| 安全 | session_id 格式 | UUID v4，不可猜测 | 单元测试 |
| 安全 | 对话历史 | 不在日志中记录用户消息原文 | 日志审计 |
| 隐私 | 用户数据不用于训练 | OpenRouter `data-collection: deny` | 请求头审计 |
| 合规 | 守卫规则覆盖率 | 6/6 规则在系统提示中存在 | SC-7 自动化测试 |

**OpenRouter 隐私请求头（P1 起必须设置）：**

```python
headers = {
    "HTTP-Referer": "https://propertyai.com.au",
    "X-Title": "PropertyAI",
    "X-Data-Collection": "deny"
}
```

---

## 26. P1 Deployment Notes

### 26.1 Docker Compose（P1 新增服务配置）

```yaml
services:
  app:
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/propertyai
      - DOMAIN_API_KEY=${DOMAIN_API_KEY}
      - SESSION_SECRET_KEY=${SESSION_SECRET_KEY}
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

### 26.2 Health Check 端点（P1 扩展）

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

### 26.3 P1 Project Structure 更新

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
├── services/
│   ├── llm_client.py
│   ├── borrowing_capacity.py       # S-G（P0新增）
│   ├── budget_gap_detector.py      # S-H（P0新增）
│   └── redis_client.py             # P1新增
├── routers/
│   ├── chat.py
│   └── session.py                  # P1新增：/session 端点
├── db/
│   └── session_repository.py       # P1新增：PostgreSQL 操作
└── tests/
    ├── test_extraction_schema.py
    ├── test_state_machine.py
    ├── test_system_prompt.py
    ├── test_chat_endpoint.py
    ├── test_intent_router.py
    ├── test_summary.py
    ├── test_borrowing_capacity.py   # S-G（P0新增）
    ├── test_budget_gap_detector.py  # S-H（P0新增）
    └── test_guardrail_rules.py      # P0新增
```
