# Documentation Impact Matrix

## Code Path to Documentation Mapping

Use this matrix to determine which documentation files to check when code in a given path changes.

### Backend Feature Code

| Code Path Changed | Check These Docs |
|-------------------|-----------------|
| `src/features/{feature}/` (any file) | `src/features/{feature}/README.md` |
| `src/features/{feature}/api/routes.py` | `docs/onboarding/{feature}/` FLOW docs |
| `src/features/{feature}/storage/entities/` | `docs/onboarding/{feature}/` data model sections |
| `src/features/{feature}/services/` | `docs/onboarding/{feature}/` service docs |
| New feature created | Must create `src/features/{feature}/README.md` |

### Backend Core Code

| Code Path Changed | Check These Docs |
|-------------------|-----------------|
| `src/core/auth/` | `src/core/auth/README.md`, `docs/onboarding/01-WEBSOCKET-CONNECTION.md` |
| `src/core/http/` | `src/core/http/README.md` |
| `src/core/ai/` | `src/core/ai/README.md`, `docs/onboarding/04-OPENAI-INTEGRATION.md` |
| `src/core/usage_limits/` | `src/core/usage_limits/README.md` |
| `src/core/prompts/` | `src/core/prompts/README.md` |
| `src/core/websocket/` | `docs/onboarding/01-WEBSOCKET-CONNECTION.md`, `docs/onboarding/FLOW-01-connection-establishment.md` |
| `src/core/jobs/` | Related FLOW docs that reference job processing |

### Backend Services (Cross-Cutting)

| Code Path Changed | Check These Docs |
|-------------------|-----------------|
| `src/services/session_handler.py` | `docs/onboarding/02-INTERVIEW-SESSION.md`, `docs/onboarding/FLOW-04-conversation-turn.md` |
| `src/services/interview_service.py` | `docs/onboarding/FLOW-02-interview-initialization.md` |
| `src/api/` | `docs/onboarding/00-SYSTEM-OVERVIEW.md` |

### Database and Migrations

| Code Path Changed | Check These Docs |
|-------------------|-----------------|
| `src/storage/migrations/` | `docs/onboarding/05-DATA-SERVICES.md` |
| New entity or enum | Feature-specific onboarding data model sections |

### Testing

| Code Path Changed | Check These Docs |
|-------------------|-----------------|
| `tests/` (conventions changed) | `tests/README.md`, `your test conventions doc (if any)` |
| New test patterns introduced | `your test conventions doc (if any)` |

### AI Infrastructure

| Code Path Changed | Check These Docs |
|-------------------|-----------------|
| `.claude/skills/` | `.cursor/rules.md` documentation index |
| `.cursor/rules/` | `.cursor/rules.md` documentation index |
| `.ai/` | `AGENTS.md` (if workflow sections affected) |
| `AGENTS.md` | `CLAUDE.md` (if structure changed) |

## Decision Tree: Does This Change Need a Doc Update?

```
Did you create a new feature?
  └─ YES → Create feature README.md → check if onboarding docs needed
  └─ NO ↓

Did you change an API endpoint (add/modify/remove)?
  └─ YES → Check FLOW docs and feature README
  └─ NO ↓

Did you change database schema?
  └─ YES → Check data model sections in onboarding docs
  └─ NO ↓

Did you change core infrastructure (auth, websocket, AI, HTTP)?
  └─ YES → Check core module README and related onboarding docs
  └─ NO ↓

Did you change testing conventions?
  └─ YES → Check tests/README.md and your test conventions doc (if any)
  └─ NO ↓

Did you change only internal service logic with no external behavior change?
  └─ YES → No doc update needed
  └─ NO → Check the matrix above for the specific path
```

## Examples

### Changes That NEED Doc Updates

- Added a new WebSocket event type → update FLOW docs
- Changed the authentication flow → update auth README and onboarding
- Added a new API endpoint → update feature README
- Changed job processing behavior → update relevant FLOW docs
- Created a new feature → create feature README

### Changes That DON'T Need Doc Updates

- Refactored internal service method (same external behavior)
- Fixed a bug that docs never described
- Added logging or metrics
- Changed test implementation (not conventions)
- Updated dependencies in pyproject.toml
