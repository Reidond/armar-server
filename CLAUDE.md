# CLAUDE.md
@AGENTS.md

## Project

**armar-server** is a uv-managed Python CLI that runs a modded **Arma Reforger dedicated server** in a
container (Podman/Docker). It parses mods from Arma Workshop URLs (e.g.
`https://reforger.armaplatform.com/workshop/6922BD179EEDD0D2`), resolves their dependency closure,
pins versions into `armar.lock`, renders the Reforger JSON config, and installs/runs the server.

- Run everything through **uv** (`uv sync`, `uv run armar …`, `uv run pytest`).
- Authoritative Arma references live in `docs/` (BI wiki PDFs). See `AGENTS.md` → *Arma Reforger domain knowledge*.

## Skills

### User-Invocable (use with `/skill-name`)
- `/commit-message` (task) — Generate conventional commit messages
- `/spec-driven-dev` (workflow) — Spec-driven development pipeline
- `/post-task-review` (workflow) — 8-step post-task review pipeline
- `/skill-creator` (task) — Interactive skill building guide
- `/skill-creation-workflow` (workflow) — Research-backed skill creation pipeline (research + build + structural review + content review)
- `/skill-reviewer` (review) — Audit skills and determine workflow placement
- `/learning-consolidator` (workflow) — Weekly deep-analysis of learnings with promotion to rules/skills
- `/review-prompts` (workflow) — Comprehensive prompt review from engineering + domain expert perspectives
- `/analyze-logs` (task) — Root cause analysis from GCP structured logs with task file creation
- `/product-brief` (task) — Product brief with assumption-challenging and UX content for team task descriptions
- `/session-retrospective` (task) — Analyze Claude Code session history for patterns, feedback, and workflow improvements
- `/branch-switch` (task) — Safely stash, switch branch, and apply stash with conflict detection
- `/research-source-planner` (task) — Before parallel deep research, build a deduplicated, single-owner source manifest (gather → SIFT challenge → dedup → topic-clustered disjoint assignment). Pairs with `/research-source-claim`.
- `/research-source-claim` (task) — Consumer protocol for a fan-out agent/session: work ONLY your assigned manifest sources, never analyze another owner's. Consumes a `research-source-planner` manifest.
- `/parallel-deep-research` (workflow) — One-command parallel deep research with NO duplicated source analysis: scope → plan sources (research-source-planner) → fan out one sub-agent per owner (research-source-claim) → synthesize a cited report. For a single-agent lookup, use the built-in deep-research.

### Auto-Loaded by Claude (background knowledge for this project)
- `python-best-practices` (reference) — Modern Python 3.12+ conventions (auto-loads when writing/reviewing Python)
- `uv-python-tooling` (reference) — uv is mandatory for all Python operations (deps, runs, envs)
- `test-conventions` (reference) — Integration-first, DI-based mocking test conventions
- `vertical-slice` (reference) — Feature-sliced layout + layer separation patterns
- `qtquick2` (reference) — Idiomatic QtQuick 2 + QML as used in KDE apps (auto-loads when writing/reviewing `.qml` or QtQuick code)
- `kirigami` (reference) — Kirigami framework + KDE Human Interface Guidelines (auto-loads on Kirigami/KDE UI code)
- `flatpak-development` (reference) — Flatpak packaging, sandboxing & Flathub publishing (auto-loads on manifests, `finish-args`, `*.metainfo.xml`, Flathub submissions)

### Internal Pipeline Skills (invoked by workflows or directly by the model; hidden from the `/` menu)
- plan-critic (review) — Self-review spec documents before presenting
- task-learnings (task) — Extract and record project learnings
- skill-researcher (task) — Deep domain/problem research for skill creation
- skill-content-reviewer (review) — Content quality verification against research brief
- ai-changelog (task) — Append structured entries to AI infrastructure changelog
- ai-improvement-tracker (task) — Record testable hypotheses for AI infrastructure changes

> Note: the prompt-review skills (`review-prompts`, `prompt-eng-reviewer`, `prompt-domain-reviewer`,
> `prompt-engineering-conventions`) are available but **not applicable** — this project has no AI/LLM
> prompt templates.
