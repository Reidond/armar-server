# Design: multi-server-desktop

> Satisfies `requirements.md`. This is the integrated design produced by a 10-dimension
> design+critique workflow, a cross-cutting consistency pass, and two de-risking spikes.
> Status: design-complete, buildable.

## Technical Approach

Turn the single-server `armar` CLI into a **fleet tool**: a Kirigami/PySide6 **desktop app**
manages **N servers across M machines** by speaking HTTP+SSE to a small **`armar-agentd`** on each
machine **over an SSH tunnel**. The existing `config`/`workshop`/`server` services are reused
verbatim behind a new **multi-server instance model**; nothing is rewritten to async (blocking
subprocess/HTTP calls are wrapped off the event loop).

**Transport (locked).** No public ports, no TLS, no network bearer token. **Remote** machines run
`armar-agentd` on **loopback TCP + a mandatory token** — an `ssh -L` local-forward is TCP→TCP, so the
remote end must listen on loopback TCP; the **local** machine runs the agent on a **unix-domain socket
with the token disabled**. `AgentSettings` rejects any non-loopback/wildcard bind. The desktop opens an
**SSH local-forward using the user's existing keys/agent** (asyncssh) and talks HTTP+SSE over the
tunnel; the local machine reaches its agent over the UDS with no SSH.

**Trust spine.** `SSH login uid == armar-agentd uid == rootless-podman uid` (the agent runs as
`systemd --user` + linger). The agent can do nothing the SSH user could not already do — there is
no privilege boundary to defend, which is what keeps the whole design simple.

```
┌──────────────── Desktop (Flatpak, KDE runtime) ────────────────┐
│ armar-manager (PySide6 + Kirigami)                              │
│   QML pageStack ⇄ view-models (wrap armar_server.contracts DTOs)│
│        │ qasync (one shared Qt+asyncio loop)                    │
│   AgentClient (Protocol, Qt-free async)                         │
│     └─ HttpAgentClient (httpx + SSE, imports contracts)         │
└────────│──────────────────────────────│───────────────────────┘
  local: loopback/UDS (no SSH)          │ remote: ssh -L 127.0.0.1:0
                                        ▼  (asyncssh, ssh-agent, ~/.ssh ro)
┌──────── Managed machine (local OR remote, OUTSIDE the sandbox) ─┐
│ armar-agentd (uvicorn; systemd --user + linger)                │
│   routes → JobManager (async, per-instance lock, timeouts)     │
│   reuse → armar_server.{config.loader, server.*, workshop.*}    │
│   InstanceRegistry → InstanceLayout → build_run_argv (pure)     │
│        └─► rootless Podman/Docker → armar-<slug> containers      │
│            (Reforger auto-downloads game.mods[] on startup)     │
└─────────────────────────────────────────────────────────────────┘
```

### Repo / uv-workspace layout

Virtual workspace root (no `[project]`), one `uv.lock`, one shared `.venv`. **Build backend =
`hatchling.build` + `uv-dynamic-versioning` for every member** (uv still drives build/lock/run).

```
armar/                          # virtual root: [tool.uv.workspace], shared ruff/basedpyright/pytest, dev+lint groups
├─ packages/
│  ├─ armar-core/               # dist armar-core, IMPORT PACKAGE armar_server (module-name override)
│  │  └─ src/armar_server/
│  │     ├─ config/             # + instance.py, ports.py, registry.py, InstanceManifest
│  │     ├─ workshop/ server/   # unchanged services; launcher retargeted to InstanceLayout
│  │     ├─ contracts/          # NEW shared pydantic DTOs + IntEnum state enums + PROTOCOL_VERSION
│  │     └─ cli.py __main__.py errors.py logging.py net.py
│  ├─ armar-cli/                # owns the `armar` script -> armar_server.cli:app ; dep armar-core[cli]
│  ├─ armar-agentd/             # import armar_agentd ; dep armar-core + fastapi + uvicorn
│  │  └─ src/armar_agentd/{app.py,__main__.py,routes/,jobs/,security/,bootstrap/,logstream.py}
│  └─ armar-manager/            # import armar_manager ; dep armar-core + PySide6 + asyncssh + httpx
│     └─ src/armar_manager/{app.py,__main__.py,transport/,bridge/,onboarding/,secrets/,i18n.py,qml/,data/}
├─ install/install.sh           # CD artifact: bootstrap uv+podman, uv tool install armar-agentd==<ver>
├─ flatpak/io.github.<owner>.ArmarManager.{yaml,desktop,metainfo.xml,svg} + python3-deps.json
├─ scripts/{release.py, gen-flatpak-deps.sh}
└─ .github/workflows/{ci.yml, cd.yml}
```

Why the split: the **agent wheel stays lean** — `typer`/`rich` are a core `[cli]` extra, so bare
`armar-core` (what the agent depends on) pulls only httpx/pydantic/pydantic-settings/tomli-w. The
import root stays `armar_server` (via `[tool.hatch.build.targets.wheel] packages=["src/armar_server"]`),
so existing tests/imports keep working.

For the lean wheel to actually hold, `logging.py` must be **rich-free on the always-imported path**:
today `logging.py` does a top-level `from rich.logging import RichHandler`, and `workshop/resolver.py`
(reused verbatim by the agent) imports `..logging` — so leaving it as-is would drag `rich` into bare
`armar-core` and break the agent's `/resolve` path. Fix in Foundations: lazy-import `RichHandler`
inside `setup_logging` (CLI-only) and keep `get_logger` import-light. A Foundations smoke imports
`armar_server.workshop.resolver` + `armar_server.config.loader` from a **bare `armar-core` venv (no
`[cli]`)** to enforce this contract.

## Component Design

### New Files

| File Path | Purpose |
|-----------|---------|
| `packages/armar-core/src/armar_server/config/instance.py` | `InstanceLayout` Protocol, `InstanceSettings` (`.legacy(base)`, `.from_manifest(base, manifest)`), `validate_slug` |
| `…/config/ports.py` | Pure `PortAllocator` (smallest `n` with disjoint `{game,a2s,rcon}+n*step`) |
| `…/config/registry.py` | `InstanceRegistry` (on-disk CRUD, atomic `create()` under a file lock); `InstanceManifest` |
| `…/contracts/__init__.py`, `…/contracts/models.py`, `…/contracts/enums.py` | Shared pydantic DTOs (`InstanceSummary/Detail`, lifecycle, `StatusView`, `LogEvent`, `JobView`, `AppConfigView`/`AppConfigUpdate` with `SecretStr`, `AgentInfo`), `IntEnum` state enums, `PROTOCOL_VERSION` |
| `packages/armar-cli/src/armar_cli/__init__.py` + `pyproject.toml` | Owns the `armar` script (`armar_server.cli:app`) |
| `packages/armar-agentd/src/armar_agentd/app.py` | FastAPI app factory + DI wiring + `ArmarError` handler |
| `…/armar_agentd/routes/*.py` | host/doctor, instances, mods, config, scenarios, lifecycle, jobs |
| `…/armar_agentd/jobs/manager.py` | `JobManager` (async, per-instance lock, timeouts, ring buffer, SSE) |
| `…/armar_agentd/security/{settings.py,token.py}` | `AgentSettings` (loopback-only validator), `require_token`, `TokenStore` |
| `…/armar_agentd/bootstrap/{install.py,systemd.py}` | `armar-agentd install/uninstall/token`, hardened unit, `enable-linger` |
| `…/armar_agentd/logstream.py` | fan-out `podman logs -f` → N SSE subscribers |
| `packages/armar-manager/src/armar_manager/transport/{client.py,http.py,tunnel.py,connection.py,manager.py,hostkeys.py}` | `AgentClient` Protocol, `HttpAgentClient`, `AsyncSshTunnel`, `MachineConnection`, `ConnectionManager`, `HostKeyPinner` |
| `…/armar_manager/bridge/*.py` | `QAbstractListModel`s + `QObject` view-models wrapping contracts DTOs |
| `…/armar_manager/i18n.py` | Tiny `i18n` shim QObject for kirigami-addons (see *Spike 2*) |
| `…/armar_manager/qml/*.qml` | `Main.qml`, page + dialog + component QML (`qsTr()` strings) |
| `install/install.sh`, `scripts/release.py`, `scripts/gen-flatpak-deps.sh` | onboarding + release + flatpak deps |
| `flatpak/io.github.<owner>.ArmarManager.{yaml,desktop,metainfo.xml,svg}` | Flatpak manifest + desktop integration |
| `.github/workflows/cd.yml` | preview-on-main + tag-release |

### Modified Files

| File Path | Change Description |
|-----------|--------------------|
| `pyproject.toml` (root) | Becomes a **virtual workspace root**: drop `[project]`/`[build-system]`/`[project.scripts]`; add `[tool.uv.workspace]` + workspace `[tool.uv.sources]`; repath shared `[tool.ruff]`/`[tool.basedpyright]`/`[tool.pytest.ini_options]` to `packages/*`; add `lint` group |
| `src/armar_server/**` → `packages/armar-core/src/armar_server/**` | `git mv` verbatim (no code edits) |
| `tests/**` → `packages/armar-core/tests/**` | `git mv`; convert `factories` to a tests package / conftest fixtures (~2 import edits for `--import-mode=importlib`) |
| `config/settings.py` | Keep `AppSettings` (now the "legacy default" layout); ensure its layout members are read-only `@property` so it structurally conforms to `InstanceLayout` |
| `server/launcher.py`, `server/systemd.py` | Accept an `InstanceLayout` parameter; `unit_name(inst)` = `armar` (legacy) / `armar-<slug>` |
| `cli.py` | Add `armar --version`, global `-I/--instance`, `armar instance create|list|show|remove|adopt-default`; backport `loginctl enable-linger` into `service install` |
| `logging.py` | Make rich-free on the import path: lazy-import `RichHandler` inside `setup_logging` (CLI-only); keep `get_logger` dependency-light so bare `armar-core`/the agent can import `resolver`/`loader` without `rich` |
| `__init__.py` | Drop the hardcoded `__version__ = "0.1.0"`; derive from `importlib.metadata.version("armar-core")` so dynamic versioning is the single source of truth |
| `.github/workflows/ci.yml` | Repath; core matrix excludes PySide6 at collection; add offscreen `desktop-test` (KDE SDK image), `audit`, gitleaks, ruff `S`, flatpak-build jobs; keep `ci-ok` aggregator |
| `AGENTS.md`, `CLAUDE.md`, `README.md`, `.claude/skills/*` | grep-and-fix hardcoded `src/`+`tests/` paths to the new workspace layout |

### Files NOT to Modify

| File Path | Reason to Preserve |
|-----------|-------------------|
| `config/models.py` (`ServerConfig` + nested camelCase models) | The camelCase fields map 1:1 to Reforger JSON keys; changing them breaks config render |
| `workshop/resolver.py`, `workshop/parser.py` | Reuse as-is (wrap blocking calls off-loop); the `__NEXT_DATA__` parsing is load-bearing |
| `server/runtime.py` `build_run_argv` (pure) | Reuse for argv assertions; add an `AsyncContainerRuntime` Protocol alongside, don't rewrite |
| `docker/Dockerfile`, `docker/entrypoint.sh` | Server image is independent of this work |

## Data Model Changes

The **single most important change**. Today `AppSettings` hard-codes `container_name="armar-reforger"`,
ports `2001/17777/19999`, `data_dir="data"`. Multi-server requires per-instance namespacing.

- **New entities**:
  - `InstanceManifest` (persisted `instance.toml`): `slug`, `name`, `game_port`, `a2s_port`,
    `rcon_port`, `network_mode?`, `created_at`, `schema_version`.
  - `InstanceSettings` (frozen value object implementing `InstanceLayout`): derives
    `container_name = f"{prefix}-{slug}"`, per-instance `server_dir`/`profile_dir`/`config_dir`
    under `instances_dir/<slug>/…`. `.legacy(base)` reproduces today's cwd layout byte-for-byte.
  - `InstanceRegistry`: on-disk CRUD under `instances_dir` (XDG `~/.local/share/armar/instances`),
    **atomic `create()`** (file lock → `used_ports()` → allocate → mkdir → temp-write+rename).
- **New enums** (in `contracts/enums.py`, `IntEnum`): `InstanceState`, `JobState`
  (`queued/running/succeeded/failed/cancelled`), `ConnectionState`
  (`DISCONNECTED/CONNECTING/CONNECTED/DEGRADED/RECONNECTING/FAILED`), `SseEventType`
  (`state/log/progress/result/error/end`).
- **Port-collision correctness**: `used_ports()` unions existing instances **and** the legacy cwd
  default's live ports (load cwd `server.toml` if present) and reserves the base triplet; named
  allocation starts at `n>=1`. Uniqueness is checked on the **derived `container_name`**; slugs
  `default`/`reforger` are reserved. `network_mode=host` stays the default with **distinct triplets
  per instance** (the only way to coexist under host net).
- **Migration**: `armar instance adopt-default` (ships in **Phase P1**, not later) migrates an
  existing single-server cwd into the registry **before** a second instance can collide.

## API Changes

`armar-agentd`, FastAPI under `/api/v1`. Every route DI-injects `ContainerRuntime`,
`WorkshopClient`, `InstanceRegistry`, `JobManager`, `LogStreamer` (no concrete clients in handlers).
A single `ArmarError` handler maps to `{error:{type,message,detail?}}`. `require_token` is a no-op
only when bound to UDS with token disabled.

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/healthz`, `/readyz` | liveness; runtime reachable | No (loopback) |
| `GET` | `/api/v1/info` | identity/version + `protocol_version` (**never returns the token**) | token on TCP |
| `GET` | `/api/v1/host`, `/api/v1/doctor` | host capabilities; doctor checks | Yes |
| `POST` | `/api/v1/host/build-image` | build the container image (job) | Yes |
| `GET`/`POST` | `/api/v1/instances` | list / create (auto port-alloc) | Yes |
| `GET`/`PATCH`/`DELETE` | `/api/v1/instances/{slug}` | detail / update / remove (caller guards running) | Yes |
| `GET`/`PUT` | `…/{slug}/config` | `AppConfigView` (secrets `{set:bool}`) / `AppConfigUpdate` (omit-to-keep) | Yes |
| `GET`/`POST` | `…/{slug}/render` | render preview / write `server-config.json` | Yes |
| `GET`/`POST`/`DELETE` | `…/{slug}/mods[/{mod_id}]` | list / add / remove (reuse `parse_mod_id`) | Yes |
| `POST` | `…/{slug}/resolve` | dependency closure (job; resolver off-loop, capped depth/mods) | Yes |
| `GET`/`POST` | `…/{slug}/scenarios[/scan]` | cached scenarios / network scan (job) | Yes |
| `POST` | `…/{slug}/install`,`/update`,`/up`,`/stop`,`/restart` | lifecycle (long ops → jobs) | Yes |
| `GET` | `…/{slug}/status` | `StatusView` | Yes |
| `GET`/`POST` | `/api/v1/jobs`, `/jobs/{id}`, `/jobs/{id}/cancel` | introspection / cancel (terminate process group) | Yes |
| `GET` (SSE) | `/jobs/{id}/events` | job progress; `Last-Event-ID` resume | Yes |
| `GET` (SSE) | `…/{slug}/logs/stream` | live logs via fan-out `logs -f` | Yes |
| `GET` | `/api/v1/audit` | append-only redacted mutation log | Yes |

**Job/SSE model**: long ops return `202 + JobRef{job_id}`; state machine
`queued→running→{succeeded,failed,cancelled}`; bounded ring buffer; per-instance single-slot lock
(`409`); global `asyncio.Semaphore`; per-job wall-clock timeout (today's `subprocess.run` has none);
subprocess via `create_subprocess_exec` behind an `AsyncContainerRuntime` Protocol (fakeable). SSE
uses `sse-starlette` heartbeats + `X-Accel-Buffering:no` + `Last-Event-ID` replay; one `logs -f`
per instance fanned to N subscribers, torn down on last unsubscribe.

### Desktop transport & UI

- **Transport** (`armar_manager/transport/`, 100% Qt-free pure-asyncio): `AgentClient` Protocol is
  the single seam the UI depends on; `HttpAgentClient` (remote, over the tunnel) and
  `LocalConnection` (loopback/UDS) both implement it. `AsyncSshTunnel` uses asyncssh
  (`config=[~/.ssh/config]`, `agent_path=$SSH_AUTH_SOCK`, `forward_local_port('127.0.0.1', 0, …)`).
  `HostKeyPinner` does TOFU (unknown→confirm, changed→hard-fail, match→accept) reading both a
  read-only user `known_hosts` and an app-owned writable one under XDG data. `MachineConnection` is
  a state machine with health loop + backoff that raises `ConnectionLost` mid-call.
- **UI** (Kirigami, per the `kirigami`/`qtquick2` skills — `Kirigami.Units`/`Theme`, no hardcoded
  px/colors): `GlobalDrawer` (machines) → `MachineListPage` → `ServerListPage` →
  `ServerDetailPage` with a `NavigationTabBar` over **Overview / Mods / Config / Logs**. Bridge:
  `@QmlElement` `QAbstractListModel`s (machines/servers/mods/log-ring) + `QObject` view-models that
  **wrap contracts DTOs**; state `IntEnum`s registered via `@QEnum` so QML ints == DTO ints. Config
  page = `FormCard.FormCardPage`; secrets write-only/masked. **qasync single shared loop**;
  view-model commands are `@asyncSlot`. Lifecycle keyed by **stable slug** (not row index);
  `refresh()` diffs incrementally; per-`QObject` task cancellation on teardown (PySide6
  use-after-free guard).

### Remote install & onboarding

- `install/install.sh` (POSIX, `| sh`): ensure `uv` (pinned, sha256-verified) → ensure podman →
  `uv tool install armar-agentd==$VER` (pulls `armar-core` from PyPI) → `armar-agentd install`
  → emit `AgentInfo` JSON between explicit sentinels.
- `armar-agentd install` (tested Python): render a hardened **`systemd --user`** unit →
  `loginctl enable-linger` → `daemon-reload` → `enable --now` → verify `is-active`. Conservative
  default unit (`NoNewPrivileges`, `MemoryMax`, `TasksMax`); aggressive hardening opt-in (rootless
  podman needs `~/.local/share/containers`, `$XDG_RUNTIME_DIR`, userns, `AF_NETLINK`).
- Desktop **Add-Machine** runs the bootstrap over the **same asyncssh connection** (`conn.run`),
  reads the token once via `armar-agentd token print`, stores it in the Secret Service, and
  registers `machines.toml`. The local machine's agent also runs **outside** the sandbox and is
  merely detected.

## CI/CD

Two workflows, both gated by the existing `ci-ok` aggregator.

**Mutual exclusion (why double-trigger can't happen).** A single `git push` updates exactly one
ref kind. `scripts/release.py` pushes **only a tag ref** (`git push origin vX.Y.Z`, never a branch,
never `--follow-tags`), so the branch-push (preview) trigger never sees an event — GitHub does not
"see through" a tag to its branch. The rolling `preview` tag doesn't match `v*`. Belt-and-suspenders:
distinct concurrency groups + a `git tag --points-at HEAD | grep '^v'` guard in the preview job.

```yaml
# .github/workflows/cd.yml (trigger block)
on:
  push:
    branches: [main]   # → preview job  (if: github.ref_type == 'branch')
    tags: ['v*']       # → release job  (if: github.ref_type == 'tag')
  workflow_dispatch:
concurrency: { group: cd-${{ github.ref }}, cancel-in-progress: false }
```

| Path | Trigger | Version | Publishes |
|---|---|---|---|
| **preview** | push `main` | `X.Y.Z.postN.devM+gSHA` (dynamic) | rolling GitHub **prerelease** `preview` (wheels; the Flatpak bundle is added to the preview once P4 lands) — never PyPI |
| **release** | tag `v*` | tag version | **PyPI** (`armar-core` + `armar-agentd` lockstep) + GitHub Release (notes, `SHA256SUMS`, `install.sh`) |

**Versioning** (validated in *Spike 1*): `hatchling` + `uv-dynamic-versioning`. Each member sets:

```toml
[build-system]
requires = ["hatchling", "uv-dynamic-versioning"]
build-backend = "hatchling.build"
[tool.hatch.version]
source = "uv-dynamic-versioning"
[tool.uv-dynamic-versioning]
vcs = "git"
fallback-version = "0.0.0"          # no-.git / shallow builds don't crash
[tool.uv]
cache-keys = [{ file = "pyproject.toml" }, { git = { commit = true, tags = true } }]
```

Build/release jobs use `fetch-depth: 0, fetch-tags: true`; lint/lock jobs keep the default shallow
checkout (the `lock` gate is unaffected — see *Spike 1*). Add `armar --version` (reads
`importlib.metadata`). `PROTOCOL_VERSION` is a separate integer in `contracts`. Pre-first-release:
claim PyPI names `armar-core`/`armar-agentd` + register per-project Trusted Publishers. CI
wheel-smoke installs both members from `dist/` via `--find-links` (never `dist/*.whl`).

`scripts/release.py` (PEP 723, `uv run`): pure next-semver + precondition functions (unit-tested)
behind an injectable git runner; creates an annotated tag; pushes **only the tag**.

## Flatpak Packaging

`app-id io.github.<owner>.ArmarManager`. **Target the current supported KDE branch** —
`runtime: org.kde.Platform//<current>`, `sdk: org.kde.Sdk`, `base: io.qt.PySide.BaseApp//<current>`
(the only way PySide6 and Kirigami share ONE Qt; never bundle a pip PySide6 wheel).
> **Correction (Spike 2):** do **not** pin `6.8` — it is EOL by mid-2026. Use the latest supported
> branch (6.9/6.10) and keep `base` matched to it.

```yaml
finish-args:
  - --share=network            # SSE/HTTP over the tunnel + loopback to local agent
  - --share=ipc
  - --socket=wayland  --socket=fallback-x11  --device=dri
  - --socket=ssh-auth          # forwards ssh-agent → asyncssh (default auth)
  - --filesystem=~/.ssh/config:ro
  - --filesystem=~/.ssh/known_hosts:ro
  - --talk-name=org.freedesktop.secrets   # KWallet/libsecret for the loopback token
  # NO --talk-name=org.freedesktop.Flatpak (host-spawn ssh is the non-Flathub escape hatch only)
```

Third-party wheels (`httpx`, `pydantic`, `asyncssh`, `cryptography`/`cffi`, `tomli-w`) vendored via
`gen-flatpak-deps.sh` → `uv export --no-hashes` (filter out pyside6/shiboken6) → `req2flatpak`
(wheel-first, sha256-pinned, cp31x × x86_64+aarch64). First-party code installs from source
(`pip3 install --no-deps --no-index --prefix=/app ./packages/armar-core ./packages/armar-manager`).
Desktop/icon/metainfo installed via hatchling `shared-data`. The GH-Release `.flatpak` bundle needs
a runtime remote — document `--runtime-repo=https://flathub.org/repo/flathub.flatpakrepo`. Project
needs an SPDX `license` + `LICENSE` file (metainfo requires it).

## Integration Points

- `contracts` (core) is the single wire-contract shared by `armar-agentd` (server) and
  `HttpAgentClient` (client); `config.models` (`AppConfig`/`LockFile`) reused for config payloads.
- The `InstanceLayout` Protocol is the seam between the instance model (core) and the pure builders
  (`build_run_argv`, `build_steamcmd_spec`, systemd renderers).
- The `AgentClient` Protocol is the seam between transport and UI view-models.
- The Flatpak `finish-args` are consumed by transport (ssh-auth + ~/.ssh), onboarding, and security
  simultaneously — settle before transport work begins.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `uv lock --check` churns under dynamic versioning | **None** | High | **Retired by Spike 1** — uv doesn't pin member versions; gate green per commit (incl. shallow checkout) |
| `KLocalizedContext` unavailable to Python | **Certain** | Med | **Resolved by Spike 2** — use `qsTr()`; add a ~15-line `i18n` shim for kirigami-addons |
| Pinning EOL KDE runtime 6.8 | High | Med | Target current supported branch; match `base` PySide BaseApp |
| Port collision under host networking | Med | High | Allocator unions legacy default + reserves base triplet; uniqueness on derived container_name; atomic create; `adopt-default` in P1 |
| Blocking subprocess/HTTP stalls the agent event loop | Med | High | `create_subprocess_exec`/`anyio.to_thread`; JobManager with timeouts; `AsyncContainerRuntime` Protocol |
| PySide6 imported by the core test matrix | Med | Med | Physically segregate Qt tests; core matrix `--ignore`s them; offscreen `desktop-test` job in KDE SDK image |
| asyncssh gaps (FIDO/sk- keys, ProxyCommand) | Low | Med | Document a non-Flathub `SystemSshTunnel` escape hatch (P4) |
| Secret leakage via logs/SSE/`/info` | Low | High | `SecretStr` DTOs only; on-disk stays plain str; redaction filter; token never returned by `/info` |
| Comments lost when editing `server.toml` in-app | High | Low | Accept canonicalization (tomli_w); fix the misleading `loader.save_app_config` docstring |

## Alternatives Considered

| Approach | Pros | Cons | Why Rejected/Chosen |
|----------|------|------|---------------------|
| **SSH-tunnel → loopback agentd** | Reuses SSH keys; no open port/TLS/token; live SSE | needs sshd + agent on each host | **Chosen** — best security/UX for a single operator |
| Agentless over SSH (exec `armar`) | Nothing to install but `armar` | poll-only, brittle stdout parsing, no push events | Rejected — no live status; fragile |
| Exposed HTTPS agent + token | No SSH dependency | TLS certs + firewall + token mgmt; bigger attack surface | Rejected — operational burden, internet-facing |
| **hatchling + uv-dynamic-versioning** | tag-derived versions; lock stays green | extra build dep | **Chosen** — uv_build can't do dynamic versions (Spike 1) |
| Keep `uv_build`, inject version in CI | minimal change | per-arch backend vendoring for flatpak; manual version injection | Rejected — more moving parts |
| **qsTr() + Qt Linguist (+ i18n shim)** | works in the runtime today; de-facto KDE-Python norm | manual `.ts`/`.qm`; shim for addons | **Chosen** — `KLocalizedContext` unavailable to Python (Spike 2) |
| `KLocalizedContext` (KI18n) | native KDE i18n | no Python binding; absent from runtime | Rejected — not viable for this deployment |
| **qasync single loop** | `@asyncSlot` ergonomics; transport stays Qt-free | one global loop installed in app.py | **Chosen** — simpler than a worker-thread bridge |

## Spike Results

### Spike 1 — `uv lock --check` vs dynamic versioning: **GREEN (empirical)**

Reproduced a faithful mini-workspace (root + `armar-core` + `armar-agentd`, both `dynamic=["version"]`
with `hatchling` + `uv-dynamic-versioning`) under uv 0.11.25:

- At tag `v0.1.0`, derived version = `0.1.0`; a real `uv build` stamped `armar_core-0.1.0-*.whl`.
- `uv.lock` records members as `source = { editable = … }` with **no `version =` line**.
- After a commit past the tag (version → `0.1.0.post1.dev0+gSHA`), **`uv lock --check` exited 0**.
- A **shallow checkout with no tags** + `uv lock --check` also exited 0 (derived version falls back
  to `0.0.0.…`, but the lock gate is unaffected).

Conclusion: uv does not pin dynamic workspace-member versions, so the lock gate is stable per commit.
The `uv_build → hatchling` swap is required (the plugin explicitly does not support `uv_build`).

### Spike 2 — KF6 Python bindings / i18n in the KDE runtime: **use `qsTr()`** (high confidence)

- KF6 Python bindings exist (Shiboken) but are **partial**; **KI18n / `KLocalizedContext` is not
  among them** and is **absent** from the `org.kde.Platform` runtime (PySide6 comes from
  `io.qt.PySide.BaseApp`).
- Real PySide6+Kirigami apps use `qsTr()`; **Kirigami core does not require** a `KLocalizedContext`.
- **Caveat:** kirigami-addons (`FormCard`, `AboutPage`) call `i18n()` and throw `i18n is not defined`
  without a context object → add a small `i18n` shim QObject (`@Slot` pass-throughs to
  `QCoreApplication.translate`) set via `engine.rootContext().setContextObject(shim)`.
- **Bonus:** `org.kde.Platform//6.8` is EOL by mid-2026 → target the current supported branch.
