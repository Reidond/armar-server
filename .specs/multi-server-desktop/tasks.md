# Tasks: multi-server-desktop

> Derived from `design.md`. This is an **epic**: it exceeds the single-spec soft caps (≤4 phases,
> ≤15 tasks), so this file details the **Foundations** phase fully (the next actionable work) and
> lists **P1–P4** at roadmap altitude. Each of P1–P4 should be expanded into its own
> `.specs/multi-server-desktop-pN/` spec when it is reached.

## Implementation Status (updated)

- **Phase F (Foundations): COMPLETE and green.** `uv sync`, `uv run armar --help/--version`,
  `ruff check`, `ruff format --check`, `basedpyright`, `pytest`, `uv lock --check`, and
  `uv build --all-packages` all pass. (`uv build` at the virtual root must use `--all-packages` /
  `--package`; the bare `uv build` cannot build a `[project]`-less root — CI uses the correct form.)
- **Phases P1–P4: substantially implemented ahead of their per-phase sub-specs** (core instance
  model + registry + `adopt-default`; `armar-agentd` app with auth/JobManager/instances/lifecycle/
  mods/config/scenarios/logs/jobs SSE; `install.sh` + `armar-agentd install/token/doctor`; manager
  transport + Kirigami UI shell + Mods/Config/Logs panes; `cd.yml` preview/release + `scripts/release.py`;
  Flatpak manifest + vendored deps). The full offline gate is green over all of it.
- **Sub-specs authored + implemented this session:**
  - `.specs/multi-server-desktop-p1/spec.md` — **token on the main path via Secret Service**:
    `secrets/tokens.py` (`SecretTokenStore` over keyring with an in-memory fallback) +
    `transport/connection.py` (`dial_remote`/`rotate_remote_token`); `ConnectionManager` now loads
    a stored token, obtains it once over SSH-exec (`armar-agentd token print`) when absent, persists
    it, and supports rotation. The token travels only as the `Authorization` header. Covered by
    `test_secret_token_store.py` + `test_connection.py` (Qt-free fakes).
  - `.specs/multi-server-desktop-p4/spec.md` — **distribution/ops hardening (offline slice)**:
    `install.sh` bootstraps `uv` (pinned via `UV_VERSION`) when missing and fails clearly when no
    container runtime exists; all shell scripts + both workflows are now `shellcheck`/`actionlint`
    clean (fixed a YAML-invalid step name and the bogus `package-dir` PyPI input in `cd.yml`).
- **Remaining (need external infra; tracked in the P4 sub-spec):**
  - Flatpak `keyring` vendoring (regenerate `flatpak/python3-deps.*.json`) so Secret Service works
    inside the sandbox; until then the sandbox uses the in-memory token fallback.
  - Flathub submission, the `.flatpak` bundle on the rolling `preview` prerelease, and a
    token-rotation button in QML.
  - `F0` (PyPI name claim + Trusted Publishers) remains an external prerequisite before the first tag.

## Dependency Graph

```
F1 workspace restructure ─┬─ F2 build backend + dynamic versioning ─┐
                          ├─ F3 armar-cli + [cli] extra + --version ─┤
                          ├─ F4 contracts package ───────────────────┤
                          └─ F5 test config migration ───────────────┼─ F8 GREEN GATE ─► (P1 unblocked)
F6 CI repath + cd.yml skeleton ──────────────────────────────────────┤
F7 docs grep-and-fix ────────────────────────────────────────────────┤
F0 external: claim PyPI names + Trusted Publishers ───────────────────┘  (before first tag, not first commit)

P1 connect+lifecycle  ─►  P2 logs+status  ─►  P3 mods+config  ─►  P4 polish+distribution
(needs F8 + core instance model)            (needs P1)        (needs P1)   (needs P1–P3)
```

## Phases

### Phase F (Foundations): make the workspace + tooling ready, one green commit

- **Entry criteria**: Spec approved by user.
- **Exit criteria**: `uv sync`, `uv run armar --help`, `uv run armar --version`, `ruff check`,
  `ruff format --check`, `basedpyright`, `pytest`, `uv lock --check`, and `uv build` (all members)
  **all green**; no behavioural change to the CLI.
- **Quality gate**: Full.
- **Tasks**: F1–F8 (F0 is an external prerequisite for the first *release*, not the first commit).

### Phase P1: connect machines + lifecycle (build/install/up/stop)

- **Entry criteria**: Phase F complete and green.
- **Exit criteria**: From the desktop, add a machine over SSH, create an instance, and
  build/install/up/stop it with live job progress; preview CD publishes a prerelease.
- **Quality gate**: Standard.
- **Epics**: core instance model (`instance`/`ports`/`registry` + `adopt-default`); agentd skeleton
  (auth, JobManager, instances CRUD, lifecycle, job SSE); `install.sh` + `armar-agentd install`;
  manager transport + onboarding + UI shell (MachineList/ServerList/Detail + StatusChip +
  JobProgressSheet + i18n shim) + QML load smoke; CD preview→prerelease, release→PyPI.
- **Spec-before-P1 fixes (from plan-critic)**: onboarding must obtain the agent token on the **main**
  path (not only when installing); `instance.toml`/`machines.toml` carry `schema_version` and need a
  documented downgrade/migration-back path; remote agent = loopback TCP + token, local = UDS no-token.

### Phase P2: live logs + status

- **Entry criteria**: P1 complete.
- **Exit criteria**: Live log streaming with reconnect/`Last-Event-ID`; enriched status.
- **Quality gate**: Standard.
- **Epics**: agentd `logs/stream` fan-out + steamcmd progress parse + `StatusView`; manager
  log-ring model + Overview/Logs pages + reconnect/backoff + per-`QObject` task cancellation.

### Phase P3 / P4: mods+config / polish+distribution

- **Entry criteria**: P1 (and P2 for status surfaces).
- **Exit criteria (P3)**: in-app mod add/resolve + `server.toml` editing (write-only secrets,
  `fastValidation` forced). **Exit criteria (P4)**: Flathub-ready Flatpak; token rotation; doctor.
- **Quality gate**: P3 Standard, P4 Full.
- **Epics (P3)**: agentd mods CRUD + resolve job + config GET/PUT + render; manager `ModListModel`/
  `ConfigViewModel` + AddModDialog + FormCard config page + audit surface.
- **Epics (P4)**: add an SPDX `license` + `LICENSE` file (required by the Flatpak metainfo; none
  exists today); Flatpak hatchling shared-data + Flathub submission; add the Flatpak bundle to the
  preview prerelease; token rotation UX; `armar-agentd doctor`; `SystemSshTunnel` escape hatch;
  optional TestPyPI for previews.

---

## Task List (Foundations — fully detailed)

### Task F1: Convert repo to a uv virtual workspace, move core (no code edits)

- **Size**: L
- **Depends on**: None
- **Files to modify**: root `pyproject.toml`; `git mv src/armar_server → packages/armar-core/src/armar_server`; new `packages/armar-core/pyproject.toml`
- **Files NOT to modify**: any `.py` under the moved tree (verbatim move)
- **Acceptance criteria**:
  - [ ] Root `pyproject.toml` is a virtual root (`[tool.uv.workspace] members=["packages/*"]`, workspace `[tool.uv.sources]`, shared `dev` + new `lint` groups); no `[project]`/`[build-system]`
  - [ ] `armar-core` keeps import root `armar_server` via `[tool.hatch.build.targets.wheel] packages=["src/armar_server"]`
  - [ ] `uv sync` succeeds; `uv run armar --help` works unchanged
- **Test requirements**: existing suite runs (gated by F5); no test edits here
- **Status**: [x] Done — workspace under `packages/*`, virtual root `pyproject.toml`, `armar_server` import root preserved

### Task F2: Build backend = hatchling + uv-dynamic-versioning (all members)

- **Size**: M
- **Depends on**: F1
- **Files to modify**: each member `pyproject.toml` (`build-system`, `[tool.hatch.version]`, `[tool.uv-dynamic-versioning]` with `fallback-version`, `[tool.uv] cache-keys`); `…/armar_server/__init__.py`
- **Acceptance criteria**:
  - [ ] `uv build` at a `vX.Y.Z` tag stamps wheels with that version
  - [ ] A commit past the tag changes the derived version but `uv lock --check` stays green (per Spike 1)
  - [ ] Shallow/no-tag checkout still builds (uses `fallback-version`)
  - [ ] `__init__.py` no longer hardcodes `__version__ = "0.1.0"`; it derives from `importlib.metadata` (single source of truth)
- **Test requirements**: a CI assertion that `uv lock --check` passes after a no-op commit (smoke)
- **Status**: [x] Done — every member uses `hatchling` + `uv-dynamic-versioning` with `fallback-version`; `__init__.py` derives from `importlib.metadata`

### Task F3: `armar-cli` member + `[cli]` extra + `armar --version` + rich-free import path

- **Size**: M
- **Depends on**: F1
- **Files to modify**: `packages/armar-cli/{pyproject.toml,src/armar_cli/__init__.py}`; `armar-core` `[project.optional-dependencies] cli=[typer,rich]`; `cli.py` (add `--version`); **`logging.py`** (lazy-import `RichHandler`)
- **Acceptance criteria**:
  - [ ] `armar` script resolves to `armar_server.cli:app`; bare `armar-core` install pulls no typer/rich
  - [ ] `armar --version` prints the `importlib.metadata` version
  - [ ] `logging.py` lazy-imports `RichHandler` inside `setup_logging` (CLI-only); `get_logger` stays rich-free
  - [ ] In a **bare `armar-core` venv (no `[cli]`)**, `import armar_server.workshop.resolver` and `import armar_server.config.loader` succeed without `rich` (proves the agent's reuse path stays lean)
- **Test requirements**: a test asserting `--version` output; wheel-smoke installs `armar-cli` + runs `armar --help`; a **bare-core import smoke** (no `[cli]`) covering `resolver`/`loader`
- **Status**: [x] Done — `armar-cli` owns the script; `logging.py` lazy-imports `RichHandler`; `armar --version` added; `--version` covered by `test_cli.py` + CI wheel-smoke

### Task F4: `armar_server.contracts` package (DTOs + enums + PROTOCOL_VERSION)

- **Size**: M
- **Depends on**: F1
- **Files to modify**: `…/armar_server/contracts/{__init__,models,enums}.py`
- **Files NOT to modify**: `config/models.py` (reuse `AppConfig`/`LockFile`, don't duplicate)
- **Acceptance criteria**:
  - [ ] Pure pydantic + `IntEnum`s; **no fastapi import** in core
  - [ ] `PROTOCOL_VERSION` is a single integer constant
  - [ ] DTOs: `AgentInfo`, `InstanceSummary/Detail`, lifecycle, `StatusView`, `JobView`, `LogEvent`, `AppConfigView` (`{set:bool}`), `AppConfigUpdate` (`SecretStr`, omit-to-keep)
- **Test requirements**: round-trip serialization tests for each DTO; secret fields never serialize their value
- **Status**: [x] Done — `contracts/{__init__,models,enums}.py` with `PROTOCOL_VERSION`; covered by `test_contracts.py`

### Task F5: Test configuration migration

- **Size**: M
- **Depends on**: F1
- **Files to modify**: `git mv tests → packages/armar-core/tests`; convert `factories` to a tests package / conftest fixtures (~2 import edits); root `[tool.pytest.ini_options]` (`--import-mode=importlib`, repathed `testpaths`); `[tool.basedpyright]`/`[tool.ruff]` repath
- **Acceptance criteria**:
  - [ ] `pytest` collects and passes from the new layout
  - [ ] `basedpyright src tests`-equivalent passes against `packages/*/src` + tests
  - [ ] Core test collection does **not** import PySide6 (none present yet; guard in place for P1)
- **Test requirements**: the existing 10 test modules pass unchanged except the ~2 factory imports
- **Status**: [x] Done — tests under `packages/*/tests`; `--import-mode=importlib`; core matrix does not import PySide6

### Task F6: CI repath + `cd.yml` skeleton

- **Size**: M
- **Depends on**: F1, F2, F5
- **Files to modify**: `.github/workflows/ci.yml` (repath; keep `ci-ok`; add `audit`/gitleaks/ruff-`S`; placeholder `desktop-test` wired but skipped until P1); new `.github/workflows/cd.yml`
- **Acceptance criteria**:
  - [ ] `ci.yml` green on the restructured repo
  - [ ] New gating jobs (`audit`, gitleaks, ruff-`S`) are added to `ci-ok.needs`; **`desktop-test` is present but NOT in `ci-ok.needs` until P1** (the aggregator fails on `skipped`) — or it is a trivial always-succeeds placeholder. State which in the PR.
  - [ ] `cd.yml` preview job runs on `push:main` (`ref_type==branch`), release job on `tags:v*` (`ref_type==tag`); preview guarded to skip if HEAD carries a `v*` tag
  - [ ] Build jobs use `fetch-depth:0, fetch-tags:true`; lint/lock jobs stay shallow and locked (`uv sync --only-group lint`)
- **Test requirements**: `actionlint` passes; a dry-run/`workflow_dispatch` confirms job selection (the mutual-exclusion claim is verified by selection + the `git tag --points-at HEAD` guard, not asserted as a unit test)
- **Status**: [x] Done — `ci.yml` repathed with `audit`-class jobs + `ci-ok`; `cd.yml` preview/release with the HEAD-tag guard; build jobs use `fetch-depth:0`/`fetch-tags:true`

### Task F7: Docs grep-and-fix for the new layout

- **Size**: S
- **Depends on**: F1
- **Files to modify**: `AGENTS.md`, `CLAUDE.md`, `README.md`, `.claude/skills/*` (hardcoded `src/`+`tests/` paths)
- **Acceptance criteria**:
  - [ ] No stale `src/armar_server`/`tests/` paths that point outside `packages/*`
  - [ ] README install/quickstart reflects the workspace (`uv run armar …` still valid)
  - [ ] README `uv tool install .` updated to the workspace form (`uv tool install armar-cli`) — the root is no longer an installable package
- **Test requirements**: manual grep verification (`rg 'src/armar_server|^tests/|uv tool install'`)
- **Status**: [x] Done — README/AGENTS/CLAUDE point at `packages/*`; `uv tool install ./packages/armar-cli`

### Task F8: Green-gate verification + decisions recorded

- **Size**: S
- **Depends on**: F1–F7
- **Files to modify**: none (verification); record i18n=`qsTr`+shim and runtime-branch decisions in `design.md` (already folded in)
- **Acceptance criteria**:
  - [ ] `uv run ruff check . && uv run ruff format --check . && uv run basedpyright && uv run pytest && uv lock --check` all pass
  - [ ] `uv build` succeeds for all members; wheel-smoke runs `armar --help`/`--version`
  - [ ] Single squashed-or-clean commit; no CLI behaviour change
- **Test requirements**: full gate run recorded in the PR
- **Status**: [x] Done — full gate green (`ruff`, `ruff format --check`, `basedpyright`, `pytest` 116 passed/1 skipped, `uv lock --check`, `uv build --all-packages`)

### Task F0 (external prerequisite, before the first release tag — NOT the first commit)

- **Size**: S
- **Depends on**: —
- **Acceptance criteria**:
  - [ ] App identity decided: PyPI owner/namespace + Flatpak reverse-DNS app-id (`io.github.<owner>.ArmarManager`)
  - [ ] PyPI names `armar-core` and `armar-agentd` claimed
  - [ ] Per-project Trusted Publishers registered for the release workflow
- **Status**: [~] Partial — app identity chosen (`io.github.Reidond.ArmarManager`); PyPI name claim + Trusted Publishers remain (external, before the first `v*` tag)

## Deviations Log

| Task | Deviation | Rationale |
|------|-----------|-----------|
| F8 | "`uv build` (all members)" is run as `uv build --all-packages` (and per-`--package` in CD) | the workspace root is `[project]`-less; bare `uv build` cannot build it. CI/CD use the workspace-aware form |
| F0 | App-id finalized as `io.github.Reidond.ArmarManager` (placeholder `<owner>` resolved) | needed for the Flatpak metainfo/desktop files already committed |
| P1 | `armar-agentd` gained an explicit `serve [--bind/--uds]` subcommand + `--protocol-version` flag | the installed systemd unit's `ExecStart` referenced `armar-agentd serve …`, which did not exist — the unit would have crash-looped. Also wires the desktop SSH handshake (`armar-agentd --protocol-version`) |
| P1 | Global `-I/--instance` added to the CLI (design "Modified Files" item) routing lifecycle/config/mods at a registry instance; `instance` subcommands use the base registry | completes the multi-server CLI surface; `instance create` does not pre-write `server.toml` (run `armar -I <slug> init`), matching the agentd, which tolerates an absent `server.toml` |
| P1 | Onboarding obtains the agent token only on the install path; the main remote dial uses `token=None` (agent enforces on `/info`) | Secret-Service token persistence needs a live sshd + Secret Service to integration-test — deferred to the P1 sub-spec |
