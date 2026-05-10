# Backend Patterns

## Configuration

All configuration is defined in a single `pydantic-settings` class. Never call `os.getenv` or `os.environ` directly in business logic.

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openrouter_api_key: str
    model_strong: str = "anthropic/claude-sonnet-4-5"
    model_fast: str = "anthropic/claude-haiku-4-5"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Logging

Use `structlog` with JSON output. Every log entry related to a user session must include `session_id` as a bound context variable.

```python
import structlog

logger = structlog.get_logger()

log = logger.bind(session_id=state.session_id)
log.info("chat_request_received", module=state.current_module)
```

Do not use Python's built-in `logging` module directly. Do not log sensitive fields (API keys, salary figures).

---

## Exception Handling

### Hierarchy

```
PropertyAIException          ← base for all project exceptions
├── LLMServiceError          ← OpenRouter / model call failures
├── StateTransitionError     ← invalid module progression
└── SummaryValidationError   ← summary requested with all-None fields
```

Business logic raises typed subclasses. A single FastAPI exception handler at `main.py` converts them to HTTP responses.

### API Error Envelope

All error responses (4xx and 5xx) use this exact shape:

```json
{
  "error": {
    "code": "LLM_SERVICE_UNAVAILABLE",
    "message": "OpenRouter returned 503. Please retry.",
    "details": {}
  }
}
```

Never return raw `{"detail": "..."}` FastAPI defaults for business errors.

---

## Models Package Layout

The `models/` package is split into four semantically distinct files. Add new models to the correct file; do **not** create a catch-all `schemas.py`.

| File | Contains |
|------|----------|
| `models/base.py` | `PropertyAIBaseModel` — camelCase `alias_generator`, `populate_by_name=True`; base for all public DTOs |
| `models/conversation_state.py` | Enums (`EModule`, `EStatus`, `ESubmodel`, `ESubmodelLabel`), M1–M4 sub-models, `CollectedData`, `CompletionStatus`, `ConversationStateDTO` |
| `models/chat.py` | `ChatRequest`, `ChatResponse`, `RoutingPayload` |
| `models/summary.py` | `SummaryRequest`, `SummaryResponse` |

```python
# Correct — import from the file that owns the symbol
from models.conversation_state import CollectedData, ConversationStateDTO
from models.chat import ChatRequest, ChatResponse
from models.summary import SummaryRequest, SummaryResponse

# Incorrect — there is no models.schemas
from models.schemas import CollectedData  # ModuleNotFoundError
```

---

## Prompt Management

All LLM system prompts live exclusively in `prompts/system_prompt_builder.py`. No prompt string literals are permitted in routers, services, or any other file.

```python
# Correct
from prompts.system_prompt_builder import build_system_prompt_async

# Incorrect — prompt string inline in a router or service
system_prompt = "You are an AI property buying assistant..."
```

---

## Module Completion Rules — Centralised Registry

All required-field logic for module completion lives in `MODULE_COMPLETION_RULES` in
`conversation/state_machine.py`. Do **not** hard-code field names or completion conditions
anywhere else (e.g. routers, prompts, tests).

Each entry is a `ModuleRequirements` frozen dataclass:

```python
@dataclass(frozen=True)
class ModuleRequirements:
    submodel_attr: str                            # e.g. "m1", "m2"
    all_fields: frozenset[str]                    # every field owned by this module (routing)
    required_fields: frozenset[str]               # must be non-None for completion
    extra_check: Callable[[CollectedData], bool]  # cross-module condition; use _no_extra_check if none
```

To add a required field, update `required_fields` in the relevant `MODULE_COMPLETION_RULES` entry.
To add a new conditional requirement (e.g. "field X required only when Y == Z"), write a named
predicate function and assign it to `extra_check` — never inline the logic in `is_module_complete`.

```python
# Correct — extend the registry entry
ModuleRequirements(
    ...,
    required_fields=frozenset({"household_size", "has_children", "new_required_field"}),
    extra_check=_m2_extra_check,
)

# Incorrect — ad-hoc condition outside the registry
if module == EModule.M2_LIFESTYLE and data.m2.new_required_field is None:
    return False
```

---

## Null Safety — State Merging

When merging extracted fields into `CollectedData`, a non-`None` existing value must never be overwritten by an incoming `None`. This invariant is owned by `state_machine.py` and must not be bypassed.

```python
# Correct
if incoming_value is not None:
    current.field = incoming_value

# Incorrect
current.field = incoming_value  # could silently erase collected data
```
