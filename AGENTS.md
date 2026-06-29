# AGENTS.md

Agent instructions for **armar-server** — a uv-managed Python CLI that runs a modded
**Arma Reforger dedicated server** in a container, with mods parsed from Arma Workshop URLs.

## Project setup

### Stack

- Python ≥ 3.12 (pinned to 3.13 via `.python-version`), managed **strictly with uv**.
- CLI: **Typer** (+ Rich). HTTP: **httpx**. Models/validation: **pydantic v2** + **pydantic-settings**.
  TOML: stdlib `tomllib` (read) + `tomli-w` (write).
- Container runtime: **Podman** (default) or **Docker**, shelled out to.
- Tooling: **ruff** (lint + format), **basedpyright** (type check), **pytest** (+ pytest-httpx).

### Commands

Run from the **repository root**.

```bash
uv sync                          # create venv + install deps from uv.lock
uv run ruff check .              # lint
uv run ruff format .             # format
uv run basedpyright src tests    # type-check
uv run pytest                    # tests (offline; no network/containers)
uv run armar --help              # the CLI entry point
```

Never use `pip`, `poetry`, `pyenv`, or manual venv activation — uv only (`uv add`, `uv sync`,
`uv run`, `uv lock`). See the `uv-python-tooling` skill.

### Architecture

Feature-sliced packages under `packages/`:

- `armar-core/src/armar_server/` — `config/` (`models.py` — `AppConfig` = friendly `server.toml`;
  `ServerConfig` + nested `Game`/`Rcon`/`A2S`/`GameProperties` = the Reforger JSON, **camelCase field
  names map 1:1 to JSON keys**; `LockFile`. `settings.py` = `AppSettings` (all tunables).
  `loader.py` = TOML/lock IO + JSON render), `workshop/` (`client.py` — `WorkshopClient`
  **Protocol** + `HttpWorkshopClient`; `parse_mod_id`; `parser.py` extracts `__NEXT_DATA__` → `Asset`;
  `resolver.py` does the recursive dependency closure with cache + cycle guard, pins latest versions),
  `server/` (`config_builder.py`, `steamcmd.py`, `runtime.py` — `ContainerRuntime` **Protocol** +
  Podman/Docker; `build_run_argv` is pure, `launcher.py` = pure `RunSpec` builders, `scenarios.py`,
  `systemd.py`), `contracts/` (shared wire-contract DTOs + `IntEnum` state enums +
  `PROTOCOL_VERSION`, used by `armar-agentd` and `armar-manager`).
- `armar-cli/src/armar_cli/` — owns the `armar` script (`armar_server.cli:app`), depends on
  `armar-core[cli]`.
- `armar-agentd/src/armar_agentd/` — FastAPI service on each managed machine.
- `armar-manager/src/armar_manager/` — Kirigami/PySide6 desktop app.
- `cli.py` — thin Typer handlers that wire settings + config to services and inject dependencies.
- `docker/` — `Dockerfile` (Ubuntu 22.04 + SteamCMD + libs) and `entrypoint.sh`.

Conventions (see `python-best-practices`, `vertical-slice`, `test-conventions` skills):

- Keep CLI handlers thin; push logic into the `workshop`/`server`/`config` services.
- External clients (`WorkshopClient`, `ContainerRuntime`) are **Protocols injected via DI**.
- Read all tunables from `AppSettings` (`config/settings.py`); never read env vars directly in services,
  never use magic constants.
- Pure functions for anything that builds argv/config/JSON, so it can be asserted in tests.

### Testing

- Mock external services at the **DI boundary**: pass `FakeWorkshopClient` (see
  `packages/armar-core/tests/factories.py`) or use `pytest-httpx` for `HttpWorkshopClient`; assert
  `build_run_argv` / `RunSpec` directly instead of spawning containers.
- No live workshop calls and no containers in the test suite — use the saved-blob factories.
- Prefer integration tests covering happy path + errors + edge cases together. No perf/load tests unless asked.

### Arma Reforger domain knowledge

**Rule: verify server facts against the bundled wiki PDFs in `docs/` (or
`community.bistudio.com` → `Arma_Reforger:Server_Config` / `:Server_Hosting` / `:Startup_Parameters`)
before changing the config schema, startup args, or SteamCMD usage.** These change between game versions.

Load-bearing facts the code depends on:

- Dedicated-server SteamCMD app id is **`1874900`** (the game *client* is `1874880`). Install == update:
  `steamcmd +force_install_dir <dir> +login anonymous +app_update 1874900 validate +quit`
  (`+force_install_dir` must precede `+login`).
- A mod's id is the **hex GUID in its workshop URL**. Config `game.mods[]` entries are
  `{modId, name?, version?, required?}` (`version` omitted ⇒ latest). **Only ONE scenario runs**
  (`game.scenarioId`; no rotation). `fastValidation` must stay `true` for public servers.
- Mods are **not** fetched by SteamCMD — the server auto-downloads everything in `game.mods[]` on
  startup into the profile/addons dir (`-profile`, `-addonDownloadDir`, `-addonTempDir`).
- Workshop metadata lives in the page's `<script id="__NEXT_DATA__">` blob at `props.pageProps.asset`
  (no public REST API; dependency ids are at `dependencies[i].asset.id`, nesting transitively).

### Task documents (`tasks/`)

- One task per markdown file. Prefixes: `TECH-` (design), `STRUCT-` (refactor), `PROD-` (runtime),
  `BUG-` (fix), `FEATURE-` (new work).

### Spec documents (`.specs/`)

- Medium tasks: `.specs/{task-name}/spec.md`. Large tasks: `requirements.md`, `design.md`, `tasks.md`.
- Templates live in `.ai/templates/`.

## AI Development Workflows

### Pipeline Overview

```
PRE-PLANNING                PLANNING                    IMPLEMENTATION              COMPLETION
────────────                ─────────                   ──────────────              ──────────
/product-brief              /spec-driven-dev            [auto-loaded]               /post-task-review
(task)                      (workflow)                  python-best-practices       (workflow)
   │                           │                        uv-python-tooling              │
   └─→ tasks/FEATURE-*         ├─→ plan-critic          test-conventions               ├─→ task-learnings
                               │   (review)             vertical-slice                  │   (task)
                               │                        (references)                    │
                               └─→ .specs/{name}/                                      └─→ /commit-message
                                   (state files)                                           (task)

SKILL CREATION                          PERIODIC (weekly/biweekly)
──────────────                          ──────────────────────────
/skill-creation-workflow                /learning-consolidator   /session-retrospective
```

### Task completion checklist (mandatory)

1. **Post-task review** (major tasks: 3+ files, new feature, spec completion) — `.claude/skills/post-task-review/SKILL.md`
2. **Learnings extraction** (all tasks) — `.claude/skills/task-learnings/SKILL.md`
3. **Documentation updates** — keep `README.md` + this file in sync with the CLI/config.
4. **Re-run the gate** — `uv run ruff check . && uv run basedpyright src tests && uv run pytest`.

### Learnings system

- `.ai/learnings.md` is an intake buffer, not the knowledge store. Route durable lessons to `AGENTS.md`,
  skills, or co-located comments. Run `/learning-consolidator` periodically to drain it.

### Spec-driven development

- Small tasks (1–3 files): implement directly. Medium (4–10): `.specs/{task-name}/spec.md`.
  Large (10+): full spec with approval gates. Run `plan-critic` before presenting any plan.

## Do not

- Use `pip`/`poetry`/`pyenv` or hand-edit a venv — **uv only**.
- Read environment variables directly in services — go through `AppSettings`.
- Hardcode mod versions or the LAN IP — versions come from `armar.lock` (`armar resolve`);
  `publicAddress` is detected or configured, not baked in.
- Add mission-rotation logic — Reforger runs exactly **one** scenario.
- Set `fastValidation` to false for a public/internet server.
- Patch concrete `WorkshopClient`/`ContainerRuntime` in tests, or hit the live workshop / a real
  container in the suite — inject fakes at the Protocol boundary and use fixtures.
- Bake the server binary into the image — it installs into the mounted `data/server` volume via SteamCMD.
- Confuse app ids: `1874900` is the dedicated server, `1874880` is the game client.
- Start implementing multi-file changes without a brief plan first.
- Edit a file without re-reading it when it may have changed since your last read.
- `Read` a path before confirming it exists — use `Glob` first.
