# Requirements: multi-server-desktop

## Problem Statement

Today `armar` is a single-machine, single-server, CLI-only tool. Operating several Reforger
servers across several machines means SSHing into each box, `cd`-ing into a working directory,
running `armar` commands by hand, and reading container logs manually. There is **no fleet view,
no live status, no in-app config/mod editing**, and — critically — **no safe way to run more than
one server per machine** (the runtime hard-codes a single `container_name` and a single port
triplet `2001/17777/19999`).

This task adds a **Kirigami/PySide6 desktop app** that runs on the operator's PC and manages
**N Reforger servers across M machines** (local + remote) by talking to a small **`armar-agentd`**
on each machine over an **SSH tunnel**, while keeping the existing CLI working and reusing the
existing `config`/`workshop`/`server` services. It also adds an **easy remote install** and the
**CI/CD** (preview-on-`main` + tag-release) the project currently lacks.

Two gating assumptions were de-risked with empirical/researched spikes before this spec
(see `design.md` → *Spike Results*): dynamic versioning does **not** break the `uv lock --check`
gate, and KDE's `KLocalizedContext` is **not** available to Python so i18n uses `qsTr()`.

## Actors

| Actor | Role in this feature |
|-------|---------------------|
| Operator (User) | Runs the desktop app on their PC; adds machines, creates/controls servers, edits mods/config |
| `armar-manager` (Desktop app) | Kirigami UI + transport layer; SSH tunnel client; HTTP/SSE consumer |
| `armar-agentd` (Agent) | FastAPI service on each managed machine; reuses core services; binds loopback/UDS only |
| SSH / sshd | The sole authentication + transport boundary to remote machines |
| Container runtime | Rootless Podman (default) / Docker on each machine; runs `armar-<slug>` containers |
| Arma Workshop | Mod metadata source (`__NEXT_DATA__` blob); no public REST API |
| CI/CD (GitHub Actions) | Validates, publishes preview prereleases on `main`, real releases on `v*` tags |

## Acceptance Scenarios

### UC-01: Add (onboard) a machine

| Field | Value |
|-------|-------|
| **Primary Actor** | `armar-manager` (Desktop app) |
| **Secondary Actors** | Operator, SSH, `armar-agentd` |
| **Preconditions** | Operator has an SSH target (host/user) reachable with their key/agent |
| **Postconditions (Success)** | Machine registered in `machines.toml`; a running, version-matched agent reachable over the tunnel |
| **Postconditions (Failure)** | No partial registration; clear state shown (`unreachable` / `host-key-changed` / `agent-not-installed` / `version-skew`); no secret written on failure |
| **Trigger** | Operator submits the *Add Machine* dialog |

**Main Success Scenario:**

1. Operator enters an SSH target and confirms.
2. Desktop opens an SSH connection (asyncssh, user's `~/.ssh/config` + agent).
3. Desktop verifies the host key via TOFU (unknown → confirm; match → accept).
4. Desktop probes for `armar-agentd` over SSH-exec and performs the `protocol_version` handshake.
5. Desktop obtains the agent token over SSH-exec (`armar-agentd token print`) if not already stored, and saves it to the Secret Service.
6. Desktop opens a local-loopback port-forward and calls the token-authenticated `GET /api/v1/info`.
7. Desktop registers the machine in `machines.toml` (atomic write, non-secret).

**Alternative Flows:**

- **A1 — agent missing**: At step 4, if no agent: desktop runs the bundled `install.sh` over the
  same SSH connection (which generates the token), then resumes at step 5 (reading the freshly
  generated token via `armar-agentd token print`).

**Exception Flows:**

- **E1 — host key changed**: At step 3, if the pinned key differs: **hard-fail**, surface a
  tamper warning, register nothing.
- **E2 — version skew**: At step 4, if `protocol_version` is incompatible: refuse to connect,
  show an upgrade prompt; register nothing.

### UC-02: Create a server instance (non-colliding ports)

| Field | Value |
|-------|-------|
| **Primary Actor** | `armar-agentd` |
| **Secondary Actors** | Operator (via desktop), `InstanceRegistry` (core) |
| **Preconditions** | Machine connected; agent running |
| **Postconditions (Success)** | New instance with a unique slug, a unique derived `container_name`, and a port triplet disjoint from all existing instances **and the legacy cwd default** |
| **Postconditions (Failure)** | No instance dir, no manifest, no port reservation left behind (atomic create under a file lock) |
| **Trigger** | `POST /api/v1/instances` |

**Main Success Scenario:**

1. Desktop sends a create request (name, optional ports).
2. Agent takes the per-host file lock.
3. Core computes `used_ports()` (existing instances ∪ legacy cwd default's live ports) and allocates the next disjoint `{game,a2s,rcon}` triplet.
4. Core validates the slug and the **derived `container_name`** for uniqueness (reserved slugs: `default`, `reforger`).
5. Core writes the instance dir + `instance.toml` + starter `server.toml` via temp-write+rename, releases the lock.

**Exception Flows:**

- **E1 — slug/name collision**: At step 4, return `409`; no filesystem change.
- **E2 — no free ports / write error**: roll back; release lock; return `5xx`; registry unchanged.

### UC-03: Run a long lifecycle op as a job with live progress

| Field | Value |
|-------|-------|
| **Primary Actor** | `armar-agentd` `JobManager` |
| **Secondary Actors** | Container runtime, SteamCMD, Desktop (SSE consumer) |
| **Preconditions** | Instance exists; runtime available |
| **Postconditions (Success)** | `install`/`update`/`up` completes; job ends `succeeded`; SSE `end` emitted |
| **Postconditions (Failure)** | Job ends `failed`/`cancelled`; subprocess/process-group terminated; instance left in a consistent state |
| **Trigger** | `POST …/install` (or `/update`, `/up`) |

**Main Success Scenario:**

1. Agent acquires the per-instance single-slot lock (else `409`).
2. Agent returns `202 {job_id}`.
3. Agent runs the blocking subprocess via `create_subprocess_exec` off the event loop.
4. Agent streams `state|log|progress` events with monotonic ids over `GET /jobs/{id}/events`.
5. On completion, agent emits `result` then `end`; releases the lock.

**Alternative Flows:**

- **A1 — SSE reconnect**: if the consumer drops, it resumes with `Last-Event-ID`; missed events replay from the ring buffer.

**Exception Flows:**

- **E1 — timeout**: at step 3, if the per-job wall-clock timeout fires: terminate the process group; job → `failed`.
- **E2 — cancel**: `POST /jobs/{id}/cancel` terminates the process group; job → `cancelled`.

### UC-04: Preview-on-main vs tag-release — mutual exclusion

| Field | Value |
|-------|-------|
| **Primary Actor** | GitHub Actions |
| **Secondary Actors** | `scripts/release.py`, PyPI, GitHub Releases |
| **Preconditions** | `cd.yml` exists; PyPI names claimed; Trusted Publishers registered |
| **Postconditions (Success)** | A `main` push publishes a preview prerelease; a `v*` tag publishes a real release; **never both for one change** |
| **Postconditions (Failure)** | A failed publish leaves no half-release; the `ci-ok` gate blocks |
| **Trigger** | `git push` (branch) or `scripts/release.py` (tag) |

**Main Success Scenario (preview):**

1. Operator pushes to `main`.
2. `cd.yml` `preview` job runs (`github.ref_type == 'branch'`).
3. `uv build` produces dev-versioned wheels (`X.Y.Z.postN.devM+gSHA`).
4. Job updates the rolling `preview` GitHub **prerelease**; nothing goes to PyPI.

**Alternative Flows:**

- **A1 — release**: `scripts/release.py` pushes **only** a `vX.Y.Z` tag ref → the `release` job runs (`github.ref_type == 'tag'`), publishes `armar-core` + `armar-agentd` to PyPI in lockstep + a GitHub Release.

**Exception Flows:**

- **E1 — double-trigger attempt**: a tag push does **not** fire the branch-push trigger (one push = one ref kind), and a belt-and-suspenders guard skips `preview` if `HEAD` carries a `v*` tag → exactly one path runs.

### Story: fleet status & live logs

```gherkin
Feature: Observe the fleet

  Background:
    Given the operator has at least one connected machine with a running server

  Scenario: See live status without blocking the UI
    When the operator opens the server list
    Then each server shows a status chip (icon + label, never colour alone)
    And the UI stays responsive while status is fetched asynchronously

  Scenario: Stream logs and survive a tunnel blip
    Given the operator is viewing a server's Logs tab
    When the SSH tunnel briefly drops and reconnects
    Then the log stream resumes from the last event id
    And the connection state is surfaced as DEGRADED then CONNECTED
```

### Story: edit mods & config in-app (P3)

```gherkin
Feature: Manage mods and configuration

  Background:
    Given the operator is viewing a connected server

  Scenario: Add a mod by Workshop URL and resolve dependencies
    When the operator adds a Workshop URL and triggers resolve
    Then the dependency closure is pinned and shown as a job with progress

  Scenario: Secrets are never echoed back
    When the operator opens the Config tab
    Then password fields show only whether a value is set, never the value
    And fastValidation cannot be turned off for a public server
```

## Non-Functional Requirements

- **Performance**: No agent call blocks the Qt event loop (all async via qasync); blocking
  subprocess/HTTP work runs off-loop. Live-log first event < 2s over a healthy tunnel.
- **Security**: No public ports. SSH is the only remote path. **Remote** agents bind **loopback TCP
  + a mandatory token** (an `ssh -L` forward is TCP→TCP); the **local** agent binds a **UDS with the
  token disabled**. `AgentSettings` rejects non-loopback/wildcard binds. Secrets never logged/echoed;
  `fastValidation` forced `true`.
- **Reliability**: Tunnel auto-reconnect with backoff; SSE resumable via `Last-Event-ID`;
  per-instance single-slot job lock; atomic instance create under a file lock.
- **Scalability**: Single-operator scale — correctly handle ~10 machines × a few instances each.
  No load/perf testing required.
- **Observability**: Agent append-only **redacted** mutation audit log; structured logging on
  both sides; `armar --version` and agent `/info` expose versions + `protocol_version`.

## Scope

### In Scope

- uv **workspace** restructure into `armar-core` / `armar-cli` / `armar-agentd` / `armar-manager`
  (import name `armar_server` preserved; existing tests green with ~2 import-mode edits).
- **Multi-server instance model** in core (slug, layout, registry, port allocator, manifest) + `armar instance …` CLI + `adopt-default`.
- **`armar-agentd`** FastAPI app (lifecycle, instances, mods, config, scenarios) + SSE/job model.
- Desktop **transport** (AgentClient Protocol, asyncssh tunnel, host-key TOFU, reconnect) + **Kirigami UI** (P1–P4).
- **Remote install** `install.sh` + `armar-agentd install` (systemd --user + linger) + desktop Add-Machine.
- **CI/CD**: `cd.yml` (preview + release) + `scripts/release.py` + dynamic versioning; extended `ci.yml`.
- **Flatpak** packaging (current KDE runtime, asyncssh-in-sandbox).

### Out of Scope

- Multi-tenant / role-based access (one operator == their own SSH reach).
- Mission rotation (Reforger runs exactly **one** scenario).
- In-app RCON console (would need an audited secret-readback path) — v1 omits it.
- Baking the server binary into any image (installs via SteamCMD as today).
- Public-internet exposure of the agent (SSH tunnel only).
- Windows/macOS desktop builds (Linux/KDE first).

## Dependencies and Constraints

- **uv-only** for all Python ops; pydantic v2 + pydantic-settings; httpx; ruff + basedpyright + pytest.
- Reuse existing `config`/`workshop`/`server` services; do **not** rewrite resolver/runtime to async
  (wrap blocking calls off-loop). Preserve `ServerConfig` camelCase→JSON mapping.
- Reforger facts: dedicated server SteamCMD app id **1874900**; `game.mods[] = {modId,name?,version?,required?}`;
  one `game.scenarioId`; `fastValidation` must stay `true` for public servers; mods auto-download on startup.
- **Spike 1 (resolved)**: `hatchling` + `uv-dynamic-versioning` (uv_build cannot do `dynamic=["version"]`);
  uv does **not** pin workspace-member versions in `uv.lock`, so `uv lock --check` stays green per commit.
- **Spike 2 (resolved)**: KF6 `KLocalizedContext` has **no Python binding** and is **absent** from the KDE
  runtime → i18n uses `qsTr()`; kirigami-addons (`FormCard`/`AboutPage`) need a small `i18n` shim QObject.
- **Correction**: `org.kde.Platform//6.8` is EOL by mid-2026 → target the current supported KDE branch.
- Flatpak transport = asyncssh **in-sandbox** (no `org.freedesktop.Flatpak` portal on the Flathub build).
- **App identity is undecided**: the Flatpak reverse-DNS app-id (`io.github.<owner>.ArmarManager`) and
  the PyPI owner/namespace must be chosen before F0 (PyPI name claim) and the Flatpak metainfo. Not
  needed for the Foundations commit itself.
