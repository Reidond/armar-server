# Feature Development Standards

> Thin reference. Full patterns live in shared skills.

## Quick Rules

- Vertical Slice Architecture: each feature is self-contained with `api/`, `services/`, `storage/`.
- One class per file, file name matches class name in snake_case.
- Storage enums (`storage/enums/`) are persisted; service enums (`services/enums/`) are business-only.
- Absolute imports only via your project's package root; no relative or inline imports.
- Layer flow: API → Service → Storage. Never reverse.
- Use `__init__.py` for public API exports.
- Prompt templates live in `prompts/{feature}/` (local) and remote storage (production).

## Reference Implementation

- Example feature: `src/features/feedback/`
- Example feature: `src/features/coach/`

## Full Reference

- Vertical slice skill: `.claude/skills/vertical-slice/SKILL.md`
- Python conventions skill: `.claude/skills/python-conventions/SKILL.md`
