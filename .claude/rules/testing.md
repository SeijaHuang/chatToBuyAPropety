# Testing

## Coverage Requirements

| Module | Minimum coverage |
|---|---|
| `models/base.py` | 100% |
| `models/conversation_state.py` | 100% |
| `tools/extraction_schema.py` | 100% |
| `conversation/state_machine.py` | 100% |
| `conversation/intent_router.py` | 100% |
| `prompts/system_prompt_builder.py` | 100% |
| `routers/chat.py` | ≥ 80% |
| `services/llm_client.py` | ≥ 80% |

## Rules

- Test file names mirror the source file: `test_state_machine.py` tests `state_machine.py`.
- Test function names: `test_<behaviour_under_test>` in `snake_case`.
- LLM calls in tests must be mocked; no live API calls in the test suite.
- Each test tests one behaviour. Do not combine multiple assertions for unrelated scenarios in a single test function.
