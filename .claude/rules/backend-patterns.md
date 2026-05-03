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

## Prompt Management

All LLM system prompts live exclusively in `prompts/system_prompt_builder.py`. No prompt string literals are permitted in routers, services, or any other file.

```python
# Correct
from prompts.system_prompt_builder import build_system_prompt_async

# Incorrect — prompt string inline in a router or service
system_prompt = "You are an AI property buying assistant..."
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
