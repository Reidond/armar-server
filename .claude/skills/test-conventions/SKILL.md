---
name: test-conventions
description: >
  Testing conventions for the project backend. Integration-first philosophy,
  DI-based mocking, timeout decorators, base class rules, factory usage,
  and banned patterns. Use when writing, reviewing, or scaffolding test files.
---

# Test Conventions — Project Backend

## When This Skill Activates

- Writing or editing any file under `tests/`
- Adding new test classes or test functions
- Choosing between unit, integration, or endpoint test types
- Setting up mocks for OpenAI, GCS, or internal services
- Reviewing tests for convention compliance

---

## Philosophy

**Integration tests are the primary quality gate.**
Prefer one comprehensive test class that covers all scenarios — happy path, all
error cases, validation failures, and edge cases — over many small isolated unit tests.

**Unit tests are welcome and good.** They are not the primary driver.

**All 3rd-party services are ALWAYS mocked.** OpenAI, GCS, and internal services must
be mocked via DI overrides at the `dependencies.py` boundary. No exceptions.
A test that makes real external calls is a bug.

**No performance tests. No load tests.** This project does not track or enforce
performance thresholds in automated tests.

---

## The 4 Non-Negotiable Rules

1. **Every test has a timeout decorator.** No exceptions. Bare async tests will hang forever on deadlocks.
2. **3rd-party services use DI overrides only.** Never call `unittest.mock.patch()` on a concrete client class.
3. **Endpoint tests inherit a base class. Service/integration tests do not.**
4. **No performance tests, no load tests, no real external API calls.**

---

## Test Type Decision Table

| What you're testing | Pattern | Base class | Timeout |
|---|---|---|---|
| HTTP endpoint (CRUD, auth, validation) | Inherit base class | `BaseCRUDTest` / `BaseAuthTest` | `@fast_test(3)` |
| Service + real DB (full integration) | Standalone class | none | `@integration_test(5)` |
| Complex service flow (multi-step) | Standalone class | none | `@integration_test(15)` |
| WebSocket connection + protocol | Standalone class | none | `@websocket_test(10)` |
| Pure logic (no I/O, no DB) | Standalone class | none | `@fast_test(3)` |
| CRUD via endpoint (data persistence) | Inherit `BaseCRUDTest` | `BaseCRUDTest` | `@fast_test(3)` |

---

## Timeout Decorators

Import from `tests.utils.timeout_decorator`:

```python
from tests.utils.timeout_decorator import fast_test, integration_test, websocket_test
```

| Decorator | Default | When to use |
|---|---|---|
| `@fast_test(3)` | 3 s | Unit tests, endpoint tests, simple logic |
| `@integration_test(5)` | 5 s | Standard DB integration |
| `@integration_test(15)` | 15 s | Multi-step service flows |
| `@integration_test(20)` | 20 s | Complex workflows with many DB ops |
| `@websocket_test(10)` | 10 s | WebSocket connection and protocol tests |

Apply the decorator **directly on the test method**, below `@pytest.mark.*`:

```python
@pytest.mark.integration
@pytest.mark.asyncio
@integration_test(5)
async def test_create_interview_stores_record(self, interview_service, async_session):
    ...
```

---

## Integration Test Structure

A comprehensive integration test class covers every case in one place:

```python
class TestInterviewServiceIntegration:
    """Integration tests for InterviewService with real database."""

    @pytest.fixture
    def service(self, async_session, mock_openai_client):
        return InterviewService(db=async_session, openai_client=mock_openai_client)

    # ── Happy path ──────────────────────────────────────────────────────────

    @pytest.mark.integration
    @pytest.mark.asyncio
    @integration_test(5)
    async def test_create_stores_record(self, service, async_session):
        result = await service.create(InterviewCreate(title="Test"))
        assert result.id is not None
        # Verify DB state
        db_record = await async_session.get(ExampleEntity, result.id)
        assert db_record.title == "Test"

    # ── Error cases ─────────────────────────────────────────────────────────

    @pytest.mark.integration
    @pytest.mark.asyncio
    @integration_test(5)
    async def test_create_raises_not_found_when_candidate_missing(self, service):
        with pytest.raises(NotFoundError):
            await service.create(InterviewCreate(candidate_id=99999))

    @pytest.mark.integration
    @pytest.mark.asyncio
    @integration_test(5)
    async def test_create_raises_conflict_on_duplicate(self, service, async_session):
        existing = await InterviewFactory.create_async(async_session)
        with pytest.raises(ConflictError):
            await service.create(InterviewCreate(title=existing.title))

    # ── Edge cases ──────────────────────────────────────────────────────────

    @pytest.mark.integration
    @pytest.mark.asyncio
    @integration_test(5)
    async def test_list_returns_empty_for_new_user(self, service):
        result = await service.list(user_id=99999)
        assert result == []
```

Key structural rules:
- One fixture block at the top — all shared setup as `@pytest.fixture` methods
- Group tests with comments: happy path, error cases, edge cases
- Always verify DB state after writes (do not trust the service's return value alone)
- Use factories for test data — never raw `INSERT` statements

---

## Mocking External Services

### Rule
Mock at the DI boundary (`dependencies.py`). Inject the mock via the fixture.
Never use `unittest.mock.patch("app.features.xyz.SomeConcreteClient")`.

### OpenAI Client

```python
# In test class:
@pytest.fixture
def service(self, async_session, mock_openai_client):
    return InterviewService(db=async_session, openai_client=mock_openai_client)

# mock_openai_client is provided by conftest.py
# Configure responses:
def test_openai_response_handling(self, service, mock_openai_client):
    mock_openai_client.some_method.return_value = expected_response
    ...
```

For endpoint tests, use the `override_openai_client` fixture (auto-applies DI override to `test_app`):

```python
class TestFeedbackEndpoints(BaseCRUDTest):
    @pytest.fixture(autouse=True)
    def _apply_openai_override(self, override_openai_client):
        pass  # fixture side-effect wires up the DI override
```

### Cloud Storage (GCS)

```python
@pytest.fixture
def service(self, async_session, mock_cloud_storage_client):
    return AudioService(db=async_session, storage=mock_cloud_storage_client)

# mock_cloud_storage_client is provided by conftest.py
```

### internal services (HTTP Client)

```python
@pytest.fixture
def service(self, async_session, mock_http_client_factory):
    return PersonalizationService(db=async_session, http_factory=mock_http_client_factory)

# mock_http_client_factory is provided by conftest.py
```

### Available fixtures from `conftest.py`

| Fixture | Provides |
|---|---|
| `mock_openai_client` | `MockOpenAIClient` instance |
| `override_openai_client` | DI override for `get_openai_client` applied to `test_app` |
| `mock_ai_chat_provider` | `MockAIChatProvider` instance |
| `override_ai_chat_provider` | DI override for `get_ai_provider` |
| `mock_cloud_storage_client` | `MockStorageClient` instance |
| `override_cloud_storage_service` | DI override for `get_cloud_storage_service` |
| `mock_http_client_factory` | Mock HTTP factory for internal services |
| `override_http_client_factory` | DI override for `get_http_client_factory` |
| `personalization_service_stub` | `StubPersonalizationService` |

---

## Endpoint Tests (Base Classes)

Inherit the appropriate base class and configure three class attributes:

```python
from tests.base_tests import BaseCRUDTest, BaseAuthTest, BaseValidationTest

class TestInterviewEndpoints(BaseCRUDTest, BaseAuthTest, BaseValidationTest):
    endpoint_url = "/api/v1/interview"
    factory_class = InterviewFactory
    response_schema = InterviewResponse
    create_schema = InterviewCreate
```

| Base class | What it provides |
|---|---|
| `BaseCRUDTest` | create, list, get, update, delete tests + 404 cases |
| `BaseAuthTest` | 401 on missing / invalid / expired token |
| `BaseValidationTest` | parametrized Pydantic validation error tests |

Override `_get_create_data()` to customise the payload. Override `_setup_related_data()` for FK dependencies.

---

## Factory Usage

All test data goes through async factories. Never insert rows directly.

```python
from tests.factories.interview_factory import InterviewFactory

# Single record
interview = await InterviewFactory.create_async(session)

# Batch
interviews = await InterviewFactory.create_batch_async(session, 5)

# With overrides
interview = await InterviewFactory.create_async(session, title="Custom Title", user_id=42)
```

---

## Test Naming

```
test_<what>_when_<condition>_<expected_outcome>
```

Examples:
- `test_create_interview_when_candidate_missing_raises_not_found`
- `test_list_interviews_when_user_has_none_returns_empty`
- `test_update_interview_when_not_owner_raises_unauthorized`

For positive cases, the `when_<condition>` part can be omitted:
- `test_create_interview_stores_record`
- `test_list_interviews_returns_paginated_response`

---

## Markers

```python
@pytest.mark.unit          # fast, no I/O (also for CRUD endpoint tests)
@pytest.mark.integration   # real DB, real service stack
@pytest.mark.slow          # > 1 second
@pytest.mark.security      # auth and access control
@pytest.mark.websocket     # WebSocket protocol tests
@pytest.mark.auth          # authentication enforcement
@pytest.mark.validation    # input validation and schema
```

---

## Anti-Patterns

| Anti-pattern | Correct approach |
|---|---|
| `unittest.mock.patch("app.features.X.ConcreteClient")` | Inject mock via constructor or DI override fixture |
| Real OpenAI / GCS / internal services calls in tests | Use `mock_openai_client`, `mock_cloud_storage_client`, `mock_http_client_factory` |
| Performance benchmarks / load tests | Not done in this project — delete if found |
| `@pytest.mark.external` | External services are always mocked — marker is meaningless |
| `@pytest.mark.crud` as standalone marker | CRUD tests are unit tests — use `@pytest.mark.unit` |
| Bare `async def test_*` without timeout decorator | Always add `@fast_test(3)`, `@integration_test(5)`, or `@websocket_test(10)` |
| One assertion per test class (micro-tests) | Group all related cases in one comprehensive class |
| Raw `INSERT` / SQL in tests | Use `BaseAsyncFactory` — create via `create_async()` |

---

## Test Doubles & Fixtures (gotchas)

- **`patch()` targets the import site, not the definition.** Prefer DI overrides; but when you must
  `patch()` a non-client internal, patch where it is *used* (imported), not where it is defined or
  re-exported, or the mock silently doesn't apply. After a bulk file move, run a dedicated grep for
  `patch("app.<old_path>` across `tests/` — string targets raise no import error and fail silently —
  and include underscore-prefixed helpers (`_get_*`), which public-API grep patterns miss.
- **Removing a catch-all `@handle_errors` decorator surfaces latent fixture bugs.** A defensive
  decorator silently absorbs `TypeError`/`AttributeError` from under-specified mocks, so "passing"
  tests were buggy. Expect a wave of failures; fix the fixtures (prefer explicit
  `AsyncMock(return_value=...)` over attribute auto-creation) — do not reinstate the decorator.
- **Converting an attribute to a `@property` breaks stubs built via `object.__new__`.** Those stubs
  assign the attribute directly and now hit "property has no setter". Set the underlying state
  (`_shutdown_state = …`), not the derived alias; grep tests for write-sites when adding a property.

## Pre-Writing Checklist

Before writing any test:

- [ ] Have I identified the right test type (unit / integration / endpoint)?
- [ ] Is there already a test class for this component I should extend?
- [ ] Do I know which 3rd-party services this code calls? (mock them all)
- [ ] Have I included happy path + all error cases + edge cases in the same class?
- [ ] Does every test method have a timeout decorator?
- [ ] Am I using factories for all test data?
- [ ] Are DB state assertions present for every write operation?
- [ ] Are test names following `test_<what>_when_<condition>_<expected_outcome>`?
