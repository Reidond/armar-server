# Error Handling

> Thin reference. Full patterns live in shared skill references.

## Quick Rules

- Use shared exceptions from `app.services.utils.errors`: `BadRequestError` (400),
  `UnauthorizedError` (401), `NotFoundError` (404), `ConflictError` (409).
- NEVER use `HTTPException` for 400/401/404/409 — middleware handles shared exceptions.
- `HTTPException` is only acceptable for 422, 410, 429, 500.
- Feature-specific exceptions live in `features/{feature}/exceptions/`, one per file.
- Convert feature exceptions to shared exceptions at the API route boundary.
- Authorization: check resource exists → check ownership → proceed.

## Decorator Pattern

Each feature should have `api/decorators.py` to eliminate route boilerplate.
Reference implementation: `src/features/coach/api/decorators.py`

## Full Reference

- Detailed patterns and code templates: `.claude/skills/python-conventions/references/coding-patterns.md`
- Python conventions skill: `.claude/skills/python-conventions/SKILL.md`
