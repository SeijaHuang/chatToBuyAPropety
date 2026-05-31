# Git Workflow

## Branch Naming

| Type | Pattern | Example |
|---|---|---|
| Feature | `feature/<short-desc>` | `feature/intent-router` |
| Bug fix | `fix/<short-desc>` | `fix/null-overwrite-m4-budget` |
| Chore / tooling | `chore/<short-desc>` | `chore/add-pre-commit-hooks` |

## Commit Format — Conventional Commits

```
<type>(<optional scope>): <short description>

[optional body]
```

Allowed types: `feat` · `fix` · `chore` · `test` · `docs` · `refactor`

Examples:
```
feat(state-machine): advance module on all required fields collected
fix(chat): prevent None from overwriting collected budget_max
test(intent-router): cover Chinese-language trigger keywords
```

## PR Rules

- CI must pass (ruff + mypy + pytest).
- Minimum 1 human approval required before merge.
- One logical change per PR. Do not bundle unrelated fixes.
- `main` is always deployable.

## Pre-commit Hooks

The following hooks run on every `git commit` in order. All must pass.

1. **ruff** — format check and lint (backend only)
2. **mypy --strict** — type check (backend only)
3. **pytest** — full test suite (backend only)
4. **tsc --noEmit** — type check (frontend only, runs when `frontend/` files change)

Install: `uv run pre-commit install`

## GitHub Actions CI

Every push to a PR branch triggers:

1. `ruff check .`
2. `mypy --strict .`
3. `pytest --cov --cov-fail-under=80`

A failing check blocks merge.
