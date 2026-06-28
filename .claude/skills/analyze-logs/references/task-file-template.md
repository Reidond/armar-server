# Task File Template for Log Analysis Issues

## File Naming

Pattern: `tasks/{PREFIX}-{slug}.md`

- Slug: lowercase, hyphen-separated, 3-5 words describing the issue
- Examples:
  - `tasks/BUG-websocket-session-cleanup-failure.md`
  - `tasks/PROD-openai-timeout-retry-missing.md`
  - `tasks/TECH-storage-session-leak.md`

## Prefix Selection

| Prefix | When to Use | Example |
|--------|-------------|---------|
| `BUG-` | Confirmed bug with clear reproduction path from logs | Exception in handler, wrong status code returned |
| `PROD-` | Runtime/operational issue (performance, resources, flaky behavior) | Timeout spikes, memory growth, intermittent 503s |
| `TECH-` | Design issue that needs refactoring to prevent recurrence | Missing error handling pattern, tight coupling |
| `FEATURE-` | Missing functionality that caused the error | No retry logic, missing validation |

## Template

```markdown
# {Title — same as report issue title}

## Source
Discovered via log analysis on {YYYY-MM-DD}.
Log file: `{filename}`
Time range: {start} — {end}

## Problem
{2-3 sentences describing what's happening, from the logs perspective}

## Evidence
- **Log entries:** {count} occurrences of {error type}
- **Severity:** {severity from report}
- **Affected component:** {feature/service}
- **Code location:** `{file_path}:{line}` — {brief description}

## Root Cause
{Concise root cause explanation with code references}

## Proposed Solution
{Conceptual fix — what needs to change and why}

### Files to Modify
- `{file_path}` — {what to change}
- `{file_path}` — {what to change}

## Acceptance Criteria
- [ ] {Error no longer appears in logs under the same conditions}
- [ ] {Specific behavior is corrected}
- [ ] {Tests cover the fix scenario}
```

## Quality Rules

- Task file must be self-contained — a developer should understand the issue without reading the full log analysis report.
- Always include the source log file name and date for traceability.
- Code references must be verified against the current codebase (not just from stack traces — files may have changed).
- Acceptance criteria must be testable, not vague ("works correctly" is bad; "returns 200 with valid payload" is good).
