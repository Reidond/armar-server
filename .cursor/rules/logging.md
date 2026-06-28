# Logging Standards

> Thin reference. Full patterns live in shared skill references.

## Quick Rules

- Use `setup_logger(__name__)` from `app.core.logging` for class loggers.
- Assign to `self.logger` in `__init__`.
- Log levels: DEBUG (diagnostics), INFO (operations), WARNING (recoverable), ERROR (failures).
- Always use `extra={}` dict for structured logging (GCP Cloud Logging).
- Use `exc_info=True` for ERROR logs to include stack traces.
- NEVER log passwords, tokens, API keys, or PII.
- Use `InterviewLoggingContext` for scoped logging context in routes.

## Key Files

- Logger setup: `src/utils/logging_config.py`
- Logging context: `src/utils/logging_context.py`

## Full Reference

- Python conventions skill: `.claude/skills/python-conventions/SKILL.md`
- Detailed coding patterns: `.claude/skills/python-conventions/references/coding-patterns.md`
