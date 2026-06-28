# Code Quality Standards

> Thin reference. Full patterns live in shared skills and review processes.

## Linting (REQUIRED after every change)

1. Run `read_lints` on modified files.
2. Run `uv run ruff check src/path/to/file.py --fix`.
3. Fix any remaining issues.

## Quick Checklist

- [ ] Shared exceptions used (not `HTTPException` for 400/401/404)
- [ ] One class per file, matching snake_case name
- [ ] All imports at top of file, absolute via your project's package root
- [ ] Structured logging with `setup_logger(__name__)` and `extra={}`
- [ ] Authorization: check exists → check ownership → proceed
- [ ] Resource cleanup (sessions, clients, file handles)
- [ ] No sensitive data in logs
- [ ] Linting passed

## Self-Review Questions

- What could go wrong? Edge cases? Race conditions?
- External service unavailable — is it handled?
- Does it follow the same pattern as existing features?
- Am I raising `HTTPException` when I should use a shared exception?

## Workflow Discipline (mirrors AGENTS.md "Do not")

- **Append-heavy markdown edits** (`.ai/*.md`, `.specs/`, `research/`): copy an Edit's `old_string` **verbatim from a fresh Read** of the target region — never reconstruct it from memory. Re-read any file that may have changed (IDE-open, linter-touched, append log) right before editing.
- **Glob before Read**: don't `Read` a conventional/assumed path before confirming it exists — `Glob`/verify first.
- **Windows host + sub-agent spawns** (restate these in every Bash/Python sub-agent prompt — they are not inherited): no `/tmp` (use `.ai/tmp/` or `$env:TEMP`); set `PYTHONIOENCODING=utf-8` / ASCII stdout; pass POSIX paths to the Bash tool (not `~\…` backslashes); `python` not `python3`; never PowerShell cmdlets in the Bash tool; no `uv run` for one-off scripts on the host (use `uvx` or the `.venv` interpreter).
- **Verify structured config by parsing, not substring grep**: check a frontmatter key / JSON field / enum membership by scoping to the structural region (e.g. only the lines between the leading `---` frontmatter fences), never a whole-file content grep — which also matches files that merely *document* the key.

## Full Reference

- Post-task review (8 steps): `.claude/skills/post-task-review/SKILL.md`
- Task completion review (steps 1–6): `.kiro/steering/task-completion-review.md`
- Python conventions skill: `.claude/skills/python-conventions/SKILL.md`
- Detailed coding patterns: `.claude/skills/python-conventions/references/coding-patterns.md`
