# Coding Standards

## Design Principles

All four principles are **mandatory** and enforced during code review.

### SOLID
- **S** — Single Responsibility: each class and module has exactly one reason to change
- **O** — Open/Closed: extend behaviour through new classes or Protocol implementations, not by modifying existing ones
- **L** — Liskov Substitution: any implementation of a Protocol must be substitutable without breaking callers
- **I** — Interface Segregation: keep Protocol definitions narrow; do not force implementors to satisfy methods they do not need
- **D** — Dependency Inversion: high-level modules depend on Protocol abstractions, not on concrete classes

### DRY — Don't Repeat Yourself
No copy-paste logic. If the same logic appears more than once, extract it into a shared function or module before merging.

### KISS — Keep It Simple
Prefer the simplest correct implementation. Do not introduce an abstraction unless there is a clear, present use case. Three similar lines of code are better than a premature helper.

### Modularized
Each module owns one responsibility. Cross-module coupling is only allowed through defined Protocol interfaces. Direct imports of implementation classes across module boundaries are not permitted.

---

## Naming Conventions

| Construct | Convention | Example |
|---|---|---|
| File names | `snake_case` | `state_machine.py`, `llm_client.py` |
| Classes (general) | `PascalCase` | `ConversationState`, `ChatRouter` |
| Enum classes | `E` prefix + `PascalCase` | `EModule`, `EStatus`, `EUserIntent` |
| Enum members | `SCREAMING_SNAKE_CASE` | `M1_PROPERTY_NEEDS`, `IN_PROGRESS` |
| Protocol (interface) | `I` prefix + `PascalCase` | `ILLMClient`, `IChatService` |
| TypeVar / TypeAlias | `T` prefix + `PascalCase` | `TState`, `TResponse`, `TModel` |
| Public functions / methods | `snake_case` | `build_prompt()`, `update_state()` |
| Async functions / methods | `snake_case` + `_async` suffix | `call_llm_async()`, `chat_async()` |
| Function / method parameters | `snake_case` | `session_id`, `collected_data` |
| Private attributes / methods | `_` prefix + `snake_case` | `_session_id`, `_build_context()` |
| Module-level constants | `SCREAMING_SNAKE_CASE` | `MAX_TOKENS`, `DEFAULT_MODEL` |

### Interface Layer Rule
Always use `typing.Protocol` for interface definitions (structural subtyping — no explicit inheritance required by callers). Only use `ABC` when the base class itself provides shared default implementation.

```python
# Correct
class ILLMClient(Protocol):
    async def call_llm_async(self, messages: list[dict[str, str]]) -> str: ...

# Incorrect — do not use ABC for pure interface contracts
class BaseLLMClient(ABC):
    @abstractmethod
    async def call_llm_async(self, ...) -> str: ...
```

### No Magic Strings — Use Enums

Any string value that is reused in more than one place, used as a key/identifier, or represents a domain concept must be defined as an `StrEnum` member. Raw string literals for these cases are forbidden.

This applies to: module identifiers, status codes, role names, field attribute names, display labels, intent names, and any other categorical value.

```python
# Correct — canonical definition in models/conversation_state.py, referenced everywhere
class ESubmodel(StrEnum):
    M1 = "m1"
    M2 = "m2"

for submodel in ESubmodel:
    getattr(data, submodel)  # uses enum value "m1", "m2", ...

# Incorrect — magic string scattered across files
for attr in ("m1", "m2", "m3", "m4"):
    getattr(data, attr)
```

Enum classes belong in `models/conversation_state.py` unless they are exclusively used within a single module (in which case they live at the top of that module). When in doubt, put them in `conversation_state.py`.

### No `Literal` for Domain Values — Use Enums

`typing.Literal` is **forbidden** for categorical domain values. Use a `StrEnum` instead.

`Literal` has two fatal maintainability problems: the same set of values must be copy-pasted wherever the type is needed, and the compiler cannot catch inconsistencies between those copies.

```python
# Correct — single definition, imported everywhere
class EUserIntent(StrEnum):
    RECOMMEND_SUBURBS = "recommend_suburbs"
    LIST_PROPERTIES = "list_properties"
    PROPERTY_DETAIL = "property_detail"
    OPEN_ENDED_QUERY = "open_ended_query"

initial_intent: EUserIntent = EUserIntent.OPEN_ENDED_QUERY

# Incorrect — Literal duplicated across user_needs.py, summary.py, user_needs_builder.py
initial_intent: Literal[
    "recommend_suburbs", "list_properties", "property_detail", "open_ended_query"
] = "open_ended_query"
```

`Literal` is only acceptable for:
- Non-domain technical flags where no enum name would add clarity (e.g. `Literal[True]` as a discriminator field).
- External API contracts defined by a third-party schema that cannot be changed.

### Enum Example

```python
class EModule(str, Enum):
    M1_PROPERTY_NEEDS = "M1_PROPERTY_NEEDS"
    M2_LIFESTYLE = "M2_LIFESTYLE"
    M3_SUBURB_PREFERENCE = "M3_SUBURB_PREFERENCE"
    M4_BUDGET = "M4_BUDGET"
    COMPLETE = "COMPLETE"

class EStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    REQUIREMENTS_COMPLETE = "REQUIREMENTS_COMPLETE"
```

### Async Naming

```python
# Correct — async I/O function carries _async suffix
async def call_llm_async(messages: list[dict[str, str]]) -> str: ...

# Incorrect — async function missing suffix
async def call_llm(messages: list[dict[str, str]]) -> str: ...
```

---

## Type Annotations

- Every function signature (parameters + return type) must be fully annotated — public and private alike.
- Every local variable must be explicitly annotated, even when mypy can infer the type. This makes intent unambiguous and avoids silent widening when the right-hand side changes.
- `mypy --strict` runs in CI; a type error is a build failure.
- Use `Optional[X]` only at genuine system boundaries (user input, external API responses). Internal functions must not accept or return `None` unless the `None` case is meaningfully handled.
- TypeVar declarations go at module top-level, not inside functions.

```python
# Correct — annotation on every local variable
def classify_intent(message: str) -> EUserIntent | None:
    lower: str = message.lower()
    matched: EUserIntent | None = next(
        (intent for pred, intent in _INTENT_RULES if pred(lower, message)), None
    )
    return matched

# Incorrect — relying on inference
def classify_intent(message: str) -> EUserIntent | None:
    lower = message.lower()       # mypy infers str, but intent is invisible
    matched = next(...)           # type unclear without reading next()'s signature
    return matched
```

```python
TState = TypeVar("TState", bound=ConversationState)
TResponse = TypeVar("TResponse", bound=BaseModel)
```

---

## Code Style

### Docstrings
Google Style. Required on all public classes and public functions. One-line summary is sufficient for private helpers.

```python
def merge_collected_data(current: CollectedData, incoming: dict[str, object]) -> CollectedData:
    """Merge extracted fields into current state, preserving non-None values.

    Args:
        current: The existing collected data from conversation state.
        incoming: Raw extracted fields from the LLM tool call response.

    Returns:
        Updated CollectedData with non-None fields applied.
    """
```

### Comments
Only write a comment when the *why* is non-obvious: a hidden constraint, a subtle invariant, or a workaround for a specific external bug. Never comment on *what* the code does.

### Formatting
Ruff handles all formatting. Do not override Ruff decisions with `# fmt: skip` or `# noqa` without a documented reason in the same comment.

---

## Pydantic vs dataclass

| Use case | Tool |
|---|---|
| External / public data structure (DTO, API request/response, crosses HTTP boundary) | Pydantic `BaseModel` |
| Internal data transfer object (passes between functions/modules, never serialised to HTTP) | `@dataclass` |

Public DTOs that cross the HTTP boundary must inherit from `PropertyAIBaseModel` (from `models/base.py`) to get camelCase aliases. Internal dataclasses use `@dataclass(frozen=True)` when immutability is required.

```python
# Correct — public DTO inherits PropertyAIBaseModel
from models.base import PropertyAIBaseModel

class ChatResponse(PropertyAIBaseModel):
    reply: str
    current_module: str

# Correct — internal value object uses dataclass
from dataclasses import dataclass

@dataclass(frozen=True)
class ModuleRequirements:
    submodel_attr: ESubmodel
    required_fields: frozenset[str]

# Incorrect — internal struct using Pydantic (unnecessary overhead + camelCase aliases)
class ModuleRequirements(BaseModel):
    submodel_attr: ESubmodel
    required_fields: frozenset[str]
```
