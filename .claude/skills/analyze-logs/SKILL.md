---
name: analyze-logs
description: >
  Analyze application logs to find root causes and propose solutions. Supports GCP structured
  JSON logs (downloaded-logs-*.json) and local Docker container logs. Includes realtime session
  event analysis (VAD, speech detection, turn lifecycle, interruption patterns), parallel agent
  analysis for large files, and session lifecycle reconstruction. Identifies distinct issues,
  investigates each with codebase evidence, and produces a structured findings report with task files.
  Use when the user says "analyze logs", "check these logs", "what's wrong in the logs", "debug this",
  or provides a log file. Do NOT trigger for logging configuration, adding log statements, or
  log infrastructure changes.
argument-hint: "<log-file-path>"
metadata:
  type: task
---

# Analyze Logs — Root Cause Analysis from Application Logs

ultrathink

## When This Skill Activates

- User provides a GCP structured log file (typically `downloaded-logs-*.json`)
- User provides local Docker logs (from `docker compose logs` or a saved file)
- User asks to analyze logs, debug from logs, or find root causes
- User pastes log excerpts and asks what's wrong

## Ground Rules

1. **Read-only by default.** Never modify application code unless the user explicitly asks.
2. **Evidence-based.** Every root cause claim must reference specific code locations found via codebase search. If evidence is insufficient, say so and ask clarifying questions.
3. **Separate issues.** Logs often contain multiple unrelated problems. Investigate and report each one independently.
4. **Ask when unsure.** If a log entry is ambiguous, the context is unclear, or multiple root causes are plausible, ask the user rather than guess.
5. **No speculation without labeling.** If you form a hypothesis without hard evidence, explicitly mark it as `[HYPOTHESIS]` and explain what evidence would confirm or refute it.

## Analysis Pipeline

### Step 0: Load Known Issues

Before analyzing logs, read `.ai/learnings.md` to load accumulated project knowledge.
Known bug patterns, past root causes, and architectural pitfalls recorded there can
shortcut investigation and avoid re-discovering known issues.

### Step 1: Ingest and Detect Format

Read the log file: `$ARGUMENTS`

If `$ARGUMENTS` is empty or missing, ask the user for the file path.

**Auto-detect the log format** by examining the first few lines:

| Format | Detection Signal | Parser |
|--------|-----------------|--------|
| **GCP structured JSON** | Array of objects with `severity`, `timestamp`, `resource` fields | See [references/gcp-log-fields.md](references/gcp-log-fields.md) and [references/gcp-query-templates.md](references/gcp-query-templates.md) |
| **Docker compose logs** | Lines prefixed with `container-name \|` or `container-name-1  \|`, plain text with Python logging format | See [references/docker-log-format.md](references/docker-log-format.md) |
| **Plain application logs** | Python logging format: `LEVEL: module: message` or uvicorn-style output | Treat as Docker without container prefix |

**Realtime session logs:** If log entries contain `event_type` values like `speech_started`, `turn_started`, `response_created`, `session_started`, or similar realtime session events, load [references/realtime-session-events.md](references/realtime-session-events.md) — it contains the full event vocabulary, timing analysis protocol, and known failure patterns for OpenAI Realtime API sessions.

**Actions:**
1. Read the file using the Read tool. For large files (>2000 lines), read the first 100 lines to detect format, then proceed with chunked reading.
2. Identify the time range covered by the logs (earliest → latest timestamp).
3. Count total entries and break down by severity level.
4. Report the overview to the user before diving in:
   ```
   Log file: {filename}
   Format: {GCP structured JSON | Docker compose | Plain application}
   Time range: {start} — {end} ({duration})
   Total entries: {count}
   Breakdown: {N} ERROR, {N} WARNING, {N} INFO, ...
   ```

### Step 1b: Parallel Deep Analysis (Large Files)

For log files with >500 entries or spanning >1 hour, launch **3 parallel Agent subprocesses** to maximize coverage and speed:

| Agent | Focus | What to Extract |
|-------|-------|-----------------|
| **Errors & Warnings** | All ERROR/WARNING entries, exceptions, tracebacks | Categorized issue list with counts, timestamps, stack traces |
| **Session Lifecycle** | Session start/end, connection lifecycle, cleanup | Per-session timeline, anomalies, incomplete sessions |
| **Behavioral Patterns** | Timing analysis, realtime events, cross-session patterns | Interruption incidents, VAD false positives, timing gaps |

Each agent reads the **entire** file in chunks and returns structured findings. After all agents complete, merge their findings into the unified issue list (Step 2).

**When to use agents vs. direct analysis:**
- <500 entries, single session: analyze directly (no agents needed)
- 500-2000 entries, 2-5 sessions: launch 2 agents (errors + lifecycle)
- 2000+ entries or user reports a specific behavioral issue: launch all 3 agents

### Step 1c: Session Reconstruction

If the logs contain realtime session events (see [references/realtime-session-events.md](references/realtime-session-events.md)):

1. **Identify distinct sessions** by grouping on `trace` ID or `interview_id`/`session_id` fields
2. **Build a timeline** for each session: setup → active conversation → teardown → feedback → cleanup
3. **Flag anomalies**: missing phases, >60s gaps between expected events, premature termination
4. **Present session summary table** before diving into issues:
   ```
   | # | ExampleEntity ID | User | Duration | Questions | Status | Anomalies |
   ```

### Step 2: Identify Distinct Issues

Group log entries into distinct issues. An "issue" is a unique problem, not a unique log line.

**Grouping strategy:**
1. **By error signature** — same exception class + message pattern (ignore variable parts like IDs, timestamps).
2. **By trace/span** (GCP) or **by request flow** (Docker — correlate via `request_id`, `interview_id`, or temporal proximity within the same container).
3. **By temporal proximity** — errors within 1-2 seconds of each other from the same service are likely related.
4. **By causal chain** — an upstream error causing downstream errors is ONE issue, not multiple.

**Deduplication rules:**
- Same exception thrown N times = 1 issue with "occurred N times" note.
- A warning followed by an error in the same trace/request = 1 issue (the error, with warning as context).
- Different exceptions from the same root cause = 1 issue.

**Output a numbered issue list** before investigating:
```
Found {N} distinct issues:
1. [ERROR] {short description} — {count} occurrences
2. [WARNING] {short description} — {count} occurrences
...
```

### Step 3: Investigate Each Issue

For EACH issue, follow this investigation sequence:

#### 3a. Extract Context
- Full error message and exception type
- Stack trace (if present — in `textPayload`/`jsonPayload.message` for GCP, or inline for Docker)
- Request context: HTTP method, path, user ID, session ID
- Preceding log entries in the same trace/request (the "story" leading to the error)

#### 3b. Locate Code
- Extract file paths and line numbers from stack traces.
- Use Grep/Glob to find the relevant source files in the codebase.
- If no stack trace: search for the error message string, exception class name, or the endpoint path in the code.
- Read the relevant code sections to understand the execution flow.

#### 3c. Determine Root Cause
- Trace the code path from the entry point (route handler → service → storage/external call).
- Identify WHERE the error originates vs. where it surfaces (they're often different).
- Cross-reference with `.ai/learnings.md` — if this pattern was seen before, note it.
- Check for known patterns:
  - Missing null/None checks
  - Race conditions in async code
  - External service failures (OpenAI, GCS, internal services)
  - Database constraint violations
  - Configuration issues (missing env vars, wrong settings)
  - Session/state management bugs (especially in WebSocket flows)
  - Middleware exception handling gaps
  - Container startup/shutdown issues (Docker-specific: dependency ordering, health checks)

#### 3d. Timing Analysis (Realtime Sessions)

If the issue involves realtime session events, perform the timing analysis described in
[references/realtime-session-events.md](references/realtime-session-events.md) — specifically:

1. **Measure critical gaps** between event pairs (response_created → speech_started, etc.)
2. **Build an event sequence table** showing timestamps in milliseconds with deltas
3. **Compare against normal ranges** from the reference table
4. **Flag sub-10ms gaps** as evidence of concurrent events (race conditions, false VAD triggers)
5. **Cross-reference transcript length vs. speech duration** — very short transcripts from long speech = fragmented utterance

Present timing evidence as a table:
```
| Time | Event | Key Detail | Delta from Previous |
```

#### 3e. Assess Impact
- **Frequency**: one-off vs. recurring (check occurrence count)
- **User-facing**: does this break the user experience or is it internal?
- **Data impact**: could this cause data loss or corruption?
- **Blast radius**: one user, one feature, or system-wide?

#### 3f. Propose Solution
- Describe the fix conceptually (what needs to change, not the code diff).
- Reference the specific file(s) and function(s) that need modification.
- If multiple approaches exist, list pros/cons briefly.
- Flag if the fix requires a migration, config change, or external service update.

### Step 4: Compile Findings Report

Present findings in this format:

```markdown
# Log Analysis Report

**File:** {filename}
**Format:** {GCP structured JSON | Docker compose | Plain application}
**Time range:** {start} — {end}
**Analyzed:** {date}

## Overview
{summary paragraph — how many issues found, overall health assessment}

---

## Issue 1: {Title}

**Severity:** CRITICAL | HIGH | MEDIUM | LOW
**Occurrences:** {count}
**Affected component:** {feature/service name}

### Symptoms
{What the logs show — error messages, HTTP status codes, timing}

### Root Cause
{Evidence-based explanation with code references}

### Evidence
- `{file_path}:{line}` — {what this code does wrong}
- Log entry: `{relevant log excerpt}`

### Proposed Fix
{Conceptual solution — what to change and why}

### Task File
Created: `tasks/{PREFIX}-{slug}.md`

---

## Issue 2: {Title}
...
```

**Severity classification:**
- **CRITICAL** — data loss, security issue, or complete feature breakage
- **HIGH** — feature partially broken, user-facing errors, recurring failures
- **MEDIUM** — degraded experience, intermittent errors, non-critical warnings
- **LOW** — cosmetic issues, noisy logs, minor inefficiencies

### Step 4b: Challenge Review (Mandatory)

**Before presenting the findings report to the user**, run a self-review challenge pass inspired by
the plan-critic skill (`.claude/skills/plan-critic/SKILL.md`). This step catches assumption errors,
contradictory guidance, and missed issues.

For each reported issue, challenge:

1. **Evidence grounding**: Is the root cause verified against current code, or assumed from stack traces alone?
   Files may have changed since the log was produced.
2. **Fix correctness**: Does the proposed fix contradict any convention in AGENTS.md or `.ai/learnings.md`?
   Cross-check fix patterns against both sources — they can conflict.
3. **Issue grouping**: Are any "separate" issues actually symptoms of the same root cause? Would fixing
   one resolve another?
4. **Completeness**: Are there log patterns (zombie sessions, resource leaks, timing anomalies) that
   were noted but not tracked as issues? If they have MEDIUM+ severity, they need a task file.
5. **Hypothesis labeling**: Is every unverified claim marked `[HYPOTHESIS]`? Are there claims presented
   as facts that lack code-level evidence?

**Actions:**
- Fix any issues found (update report text, correct proposed fixes, add missing task files).
- Note significant changes made during the challenge pass in the report footer.
- If the challenge reveals a contradiction in project conventions (e.g., AGENTS.md vs learnings.md),
  flag it as a separate finding for the user.

### Step 5: Create Task Files

For each issue with severity MEDIUM or above, create a task file in `tasks/`.

**Prefix rules** (from project conventions):
- `BUG-` — confirmed bugs with clear reproduction path
- `PROD-` — production/runtime issues (performance, resource leaks, flaky behavior)
- `TECH-` — design issues that need refactoring
- `FEATURE-` — missing functionality that caused the error

See [references/task-file-template.md](references/task-file-template.md) for the template.

For LOW severity issues, mention them in the report but skip task file creation unless the user asks.

### Step 6: Ask About Unknowns

After presenting the report, if any issues were marked `[HYPOTHESIS]` or had insufficient evidence:
1. List the open questions explicitly.
2. Suggest what additional information would help (more logs, specific time ranges, reproduction steps).
3. Offer to investigate further if the user can provide more context.

## Handling Edge Cases

- **Massive log files (>5000 lines):** Read in chunks. Start with ERROR/CRITICAL entries, then pull surrounding context by trace ID or timestamp. Don't try to read the entire file at once.
- **No errors found:** Report this clearly. Look for WARNING-level patterns that might indicate brewing problems. Check for unusual latency patterns in `httpRequest.latency` (GCP) or slow response logs (Docker).
- **Logs from multiple services:** Group issues by `resource.labels.service_name` (GCP) or container name (Docker). Note cross-service issues when traces span services.
- **Truncated stack traces:** Search for the exception class in the codebase and trace likely code paths manually.
- **Repeated known issues:** If an issue matches a known pattern from `.ai/learnings.md`, reference the existing learning and check if the previous fix was applied.
- **Mixed log formats:** If a file contains both structured JSON and plain text (e.g., container startup messages before the app initializes structured logging), parse each section with the appropriate format.
- **Docker multi-container logs:** When logs come from `docker compose logs` (all containers), separate by container name prefix before analysis. Issues in different containers are separate unless causally linked.

## Analysis Quality — Good vs. Bad Examples

See [references/analysis-examples.md](references/analysis-examples.md) for calibration examples showing:
- Evidence-based root cause vs. surface-level description
- Proper hypothesis labeling vs. unfounded speculation
- Correct issue grouping vs. over-splitting

## What NOT to Do

- Do NOT modify source code unless explicitly asked.
- Do NOT create PRs, commits, or branches.
- Do NOT dismiss warnings without investigation — they often precede errors.
- Do NOT assume correlation is causation — verify causal chains in code.
- Do NOT group unrelated errors just because they happen close in time.
- Do NOT skip codebase verification — "I think the code does X" is not evidence.

## GCP Query Assistance

When the user needs to search GCP logs directly (not from a downloaded file), consult
[references/gcp-query-templates.md](references/gcp-query-templates.md) for pre-built
query templates. Always:
1. Start with the base service filter
2. Add appropriate time bounds
3. Use the right field (`jsonPayload.*` vs `textPayload`) for the search target
4. Test the query logic against downloaded logs first if available
