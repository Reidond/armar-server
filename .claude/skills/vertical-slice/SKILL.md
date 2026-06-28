---
name: vertical-slice
user-invocable: false
metadata:
  type: reference
description: |
  Enforce vertical slice architecture for Python backend features in this project.
  Covers feature directory scaffolding, layer separation (API/Service/Storage),
  one-class-per-file convention, prompt-as-view pattern, enum placement, import rules,
  and anti-patterns. Use when: creating new backend features, adding files to existing
  features, reviewing feature structure, or troubleshooting circular imports between features.
---

# Vertical Slice Architecture - Project Backend

## When This Skill Activates

- Creating a new backend feature from scratch
- Adding files (routes, services, models, entities) to an existing feature
- Reviewing or refactoring feature structure
- Resolving import errors between features

## Core Rules

1. **Feature-centric**: Code lives in `src/features/{feature_name}/`, not by technical layer.
2. **One class per file**: File named in `snake_case` matching the class. Rare exceptions only.
3. **Layer flow**: `API -> Service -> Storage`. Never reverse.
4. **No cross-feature imports**: Features talk through internal APIs or shared `core` modules.
5. **Absolute imports only**: `from {package}.features.{feature}.services import ExampleService`. No relative imports.
6. **Import from package `__init__.py`**: Not from deep file paths.

## Feature Directory Template

```
src/features/{feature_name}/
├── __init__.py
├── README.md                          # Feature docs (keep in sync with onboarding)
├── dependencies.py                    # FastAPI DI overrides
├── constants.py                       # Feature constants
├── prompts/                           # Prompt templates (if LLMs used)
│   └── {template_name}/
│       ├── system.txt                 # System instructions
│       └── user.txt                   # User data template with placeholders
├── config/
│   ├── __init__.py                    # Re-export public config API
│   ├── {feature}_settings.py          # Pydantic settings (one class)
│   ├── domain_tables.py               # Mapping/weights (optional)
│   └── business_rules.py              # Rule thresholds (optional)
├── exceptions/
│   ├── __init__.py
│   └── {exception_name}.py            # One exception class per file
├── api/
│   ├── __init__.py
│   ├── routes.py                      # Public FastAPI endpoints
│   ├── internal_routes.py             # JWT-authenticated internal endpoints
│   ├── decorators.py                  # Feature-specific auth/logging/error mapping
│   ├── converters.py                  # API model <-> service model conversion
│   ├── enums.py                       # API-layer enums (OpenAPI)
│   └── models/
│       ├── __init__.py
│       ├── {response_name}.py         # One response class per file
│       └── internal/
│           ├── __init__.py
│           └── {model_name}.py        # Internal API models
├── services/
│   ├── __init__.py
│   ├── {feature}_service.py           # Main service
│   ├── prompt_loader.py               # Prompt template loader (if LLMs)
│   ├── prompt_builder.py              # Prompt builder (if LLMs)
│   ├── enums/
│   │   ├── __init__.py
│   │   └── {enum_name}.py             # Business-only enums (one per file)
│   └── models/
│       ├── __init__.py
│       ├── ai_requests/               # DTOs for prompt building
│       │   └── {request_name}.py
│       ├── ai_responses/              # AI provider response contracts
│       │   └── {response_name}.py
│       └── internal/                  # Shared service-layer DTOs
│           └── {model_name}.py
├── storage/
│   ├── __init__.py
│   ├── enums/                         # Persisted enums (used in ORM columns)
│   │   ├── __init__.py
│   │   └── {enum_name}.py
│   ├── entities/                      # SQLAlchemy models
│   │   ├── __init__.py
│   │   └── {entity_name}.py
│   └── repositories/                  # DB access encapsulation
│       ├── __init__.py
│       └── {repository_name}.py
├── utils/
│   ├── __init__.py
│   └── {utility_name}.py
└── tests/
    ├── __init__.py
    ├── test_api.py
    ├── test_services.py
    └── test_storage.py
```

## Scaffolding a New Feature

```bash
FEATURE=my_feature
mkdir -p src/features/${FEATURE}/{api/models/internal,services/models/{ai_requests,ai_responses,internal},services/enums,storage/{entities,enums,repositories},config,exceptions,utils,tests}
find src/features/${FEATURE} -type d -exec touch {}/__init__.py \;
```

Then register the router in `src/api/api.py`:
```python
from {package}.features.{feature}.api.routes import router as {feature}_router
api_router.include_router({feature}_router, prefix="", tags=["{Feature}"])
```

## Layer Responsibilities

### API Layer
- Thin route handlers: validate input, call service, return response.
- Use feature `decorators.py` for auth token extraction, logging context, exception-to-HTTP mapping.
- Set logging context once at API entry; services log directly.
- Models optimized for HTTP: request schemas, response schemas, error responses.

### Service Layer
- All business logic and domain rules.
- Async I/O for all network/DB operations.
- Inject storage via protocols; keep testable.
- Split long workflows into helpers.

### Storage Layer
- SQLAlchemy entities, repositories, Alembic migrations.
- Repositories encapsulate all DB access; services never write raw SQL.
- Enums in `storage/enums/` are persisted and used in ORM columns.

## Enum Placement

| Enum Type | Location | Example |
|-----------|----------|---------|
| Persisted (DB columns) | `storage/enums/` | `ExampleEnum`, `FeedbackStatus` |
| Business-only | `services/enums/` | `DifficultyDelta`, `WeightLevel` |
| OpenAPI contract | `api/enums.py` or `api/models/` | Response status enums |
| WebSocket events | `core/websocket/models/` | `RealtimeOutboundEvent`, `RealtimeInboundEvent` |

Import via package: `from {package}.features.{feature}.storage.enums import ExampleEnum`

WebSocket event enums are **never** feature-specific — import from `app.core.websocket.models`.

## Core AI Provider Abstractions

AI provider implementations (protocols, client wrappers, provider-specific configs) live in
`core/ai/{capability}/`, **not** inside feature slices:

```
core/ai/
├── chat/          # ChatProtocol + OpenAIChatClient
├── realtime/      # RealtimeProtocol + OpenAIRealtimeClient
└── {capability}/  # New capabilities follow the same pattern
```

Each capability follows the pattern: `Protocol` + `Factory` + provider implementations.
Features consume these via DI; the business logic stays in the feature slice.

## External Client Layering

When an external API has more than one calling pattern, OR non-trivial policy (fail-open vs
fail-closed per error class, fire-and-forget consume, accept-both-during-a-status-migration), do NOT
let callers use the raw HTTP client — each caller will reinvent the policy and they drift. Layer it:

- `_xxx_client.py` — **private** HTTP transport (leading underscore), raises typed exceptions, returns typed models.
- `xxx_service.py` — **public** behavioral wrapper that owns the policy; the only thing routes/decorators call.
- `__init__.py` re-exports the service, its protocol, exceptions, and enums — but **not** the client.

Tests construct the service with `MagicMock(spec=Protocol)`; never patch the client. When a new system
replaces an old one, place new code under the **new** module's namespace immediately (readers grep by
domain name, not the historical path) — even if the old module is still importable.

## Prompt-as-View Pattern (LLM Features)

- **Prompts are views**: `.txt` templates format data for AI.
- **Models are DTOs**: Pydantic models structure data for prompt building and response parsing.
- Request models go in `services/models/ai_requests/`.
- Response models go in `services/models/ai_responses/`.
- Use `PromptTemplate` enum for type-safe template names.
- Use prompt loader with validation + caching.
- Centralize generation params in settings; no hardcoded temps/tokens.

### Prompt Storage

- **Local**: `prompts/{feature}/` at repo root (Docker-mounted to `/app/prompts/{feature}/`).
- **Cloud**: Same path structure in GCS bucket.
- Config: `prompts_dir = "{feature}"` in feature settings.

## Anti-Patterns (Feature-Specific)

For the full convention rules and "Do not" list, see AGENTS.md.
For import and code style examples, see the python-conventions skill.

These are vertical-slice-specific anti-patterns:

- Circular feature dependencies (features talk through internal APIs, not direct imports)
- God services (too many responsibilities — split into focused services)
- Magic strings in AI responses (use typed response models in `ai_responses/`)
- Raw dicts for prompt building (use request models in `ai_requests/`)
- Mixing AI response models with internal utility models

## Refactoring a Slice — Moves & Deletes

- **Moving an entity** into/out of a feature: update `app/storage/models/__init__.py` to re-import it
  from the new path, or Alembic autogenerate silently skips the table.
- **Before MOVING a file into a feature**, grep every consumer across `backend` AND `tests`. If any
  consumer is in `core/` or another feature, it must stay shared (`app/services/`) — moving it inverts
  the import direction. (Run plan-critic to catch these.)
- **Before DELETING "dormant/unused" infra**, grep `backend` + `tests` for the symbol — a spec's
  "this is unused" is frequently one call site stale (a guarded no-op consumer). The grep, not the
  design doc, is the source of truth.
- **Removing a system that consumed a JWT claim / request attribute**: audit the whole life cycle —
  writer → parser → storage → *readers*. If nothing reads it to make a decision anymore, delete the
  parse/propagate path in the same PR. A static grep finds the writers and echo-back layer and hides
  that the consumer is gone; grep `\.get("claim")`, `payload["claim"]`, and typed-container accesses.

## Config Pattern

```python
# config/__init__.py re-exports:
from {package}.features.{feature}.config import {Feature}Settings, CompetencyWeights, PerformanceThresholds

# Usage:
settings = {Feature}Settings()
```
