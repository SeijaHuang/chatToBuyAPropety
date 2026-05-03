# PropertyAI

An AI-powered property-buying assistant that guides users through a structured conversation to collect their property requirements, then returns a structured summary for downstream property matching.

---

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (`pip install uv`)
- Docker + Docker Compose (for Postgres and Redis)

---

## Quick Start

```bash
# 1. Start infrastructure
docker-compose up -d redis postgres

# 2. Install dependencies
cd backend
uv sync

# 3. Copy and populate environment variables
cp .env.example .env   # then fill in OPENROUTER_API_KEY

# 4. Run the dev server
uv run uvicorn main:app --reload --port 8000
```

API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | API key for OpenRouter LLM gateway |
| `MODEL_STRONG` | No | Model for complex reasoning (default: `anthropic/claude-sonnet-4-5`) |
| `MODEL_FAST` | No | Model for intent classification (default: `anthropic/claude-haiku-4-5`) |
| `REDIS_URL` | No | Redis connection string (default: `redis://localhost:6379`) |
| `DATABASE_URL` | No | Postgres connection string (default: `postgresql://user:password@localhost:5432/propertyai`) |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/v1/chat` | Send a user message; returns assistant reply + updated state |
| `POST` | `/api/v1/chat/summary` | Return structured property requirements summary |

---

## Running Tests

```bash
cd backend

# Full suite with coverage
uv run pytest

# Single file
uv run pytest tests/test_state_machine.py

# Single test
uv run pytest tests/test_state_machine.py::test_advance_on_required_fields_collected
```

---

## Linting & Type Checking

```bash
cd backend

uv run ruff check .          # lint
uv run ruff format --check . # format check
uv run ruff format .         # auto-fix formatting
uv run mypy --strict .       # type check
```

---

## Project Structure

```
backend/
├── main.py                          # FastAPI app + middleware setup
├── config.py                        # pydantic-settings config (reads .env)
├── models/schemas.py                # All Pydantic models (single source of truth)
├── tools/extraction_schema.py       # LLM tool definition for structured extraction
├── conversation/
│   ├── state_machine.py             # Module progression and state merging
│   └── intent_router.py             # User intent classification
├── prompts/system_prompt_builder.py # All LLM system prompts
├── services/llm_client.py           # OpenRouter async wrapper
├── routers/chat.py                  # /chat and /chat/summary endpoints
└── tests/
```

See `CLAUDE.md` for full coding standards and architecture details.
