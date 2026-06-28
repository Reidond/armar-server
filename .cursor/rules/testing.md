# Testing Standards

> Thin reference. Full patterns live in shared conventions.

## Quick Rules

- All tests MUST run in Docker. NEVER run pytest directly. (`make` does not work on Windows — use Docker Compose commands.)
- Timeout decorators required: `fast_test`, `integration_test`, `websocket_test`.
- External services mocked via DI overrides, never direct patching.
- Async factories for test data creation.
- Test naming: `test_<what>_<condition>_<expected>`.

## Commands (Docker only)

```bash
docker compose -f docker-compose.test.yaml run --rm test-runner-fast           # Fast tests (<1 min)
docker compose -f docker-compose.test.yaml run --rm test-unit-parallel        # Unit tests
docker compose -f docker-compose.test.yaml run --rm test-integration-sequential  # Integration tests
docker compose -f docker-compose.test.yaml run --rm test-runner-parallel       # Full CI suite
docker compose -f docker-compose.test.yaml run --rm test-runner-parallel pytest tests/path -v  # Specific file
```

## Test Organization

```
tests/
├── unit/                    # Isolated, fast, parallel
├── integration/             # Database, external services, sequential
├── property/                # Hypothesis-based property tests
├── factories/               # Test data factories
└── fixtures/                # Shared test fixtures
```

## Full Reference

- Test README: `tests/README.md`
- Test conventions: `your test conventions doc (if any)`
- Python conventions skill: `.claude/skills/python-conventions/SKILL.md`
- Project commands: `AGENTS.md`
