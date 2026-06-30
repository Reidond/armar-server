# Spec: multi-server-desktop-p1 — token on the main path (Secret Service)

> Sub-spec expanded from the parent epic `.specs/multi-server-desktop/` (Phase **P1**,
> "Spec-before-P1 fixes": *onboarding must obtain the agent token on the **main** path, not
> only when installing*). Scopes the one P1 item the parent left deferred; the rest of P1
> (instance model, agentd, transport, UI shell) already shipped.

## Problem

A **remote** `armar-agentd` listens on loopback TCP and requires a bearer **token** on every
authenticated route. Today the desktop dials a remote with `token=None`
(`transport/manager.py`), so every authenticated call would 401 unless the agent happens to be
token-disabled. The token is only generated/printed during install; there is no path that
**obtains the token on a normal connect** and no place that **persists** it. Per the parent
design the token must come over **SSH-exec** (`armar-agentd token print`) — never over HTTP —
and be stored in the freedesktop **Secret Service** (the Flatpak already has
`--talk-name=org.freedesktop.secrets`).

## Goals / Non-goals

- **Goal**: on connect, use a stored token; if none, obtain it once via SSH-exec and persist it
  to the Secret Service; send it as `Authorization: Bearer …`. Support token **rotation**
  (`armar-agentd token rotate`) with re-persist + reconnect.
- **Goal**: keep the transport layer **Qt-free** and unit-testable with fakes (no live sshd, no
  D-Bus in tests).
- **Non-goal**: any HTTP endpoint that returns the token (token stays on SSH-exec + the auth
  header only). Local UDS stays token-disabled. No Flathub/flatpak-deps work (that is P4).

## Design

- **`secrets/tokens.py`** (Qt-free):
  - `TokenBackend` Protocol: `get(key) -> str | None`, `set(key, value)`, `delete(key)`.
  - `KeyringTokenBackend` — **lazy** `import keyring`; service name `armar-manager`. If keyring or
    a Secret Service backend is unavailable at runtime, callers fall back (see below).
  - `InMemoryTokenBackend` — process-local; used in tests and as the graceful fallback when
    keyring raises (logged once, tokens not persisted across restarts).
  - `SecretTokenStore(backend?)` — picks `KeyringTokenBackend` by default, **falling back to
    `InMemoryTokenBackend` if keyring import/instantiation fails**; `get_token/set_token/
    delete_token(machine_name)`.
- **`transport/connection.py`** (Qt-free):
  - `Tunnel` Protocol (`open()→spec`, `exec(cmd)→(code,out,err)`, `close()`), satisfied by
    `AsyncSshTunnel`/`SystemSshTunnel`.
  - `async dial_remote(machine, *, token_store, protocol_version, tunnel_factory, client_factory)
    -> DialResult(client, tunnel)`: open tunnel → token = store.get or
    `exec("armar-agentd token print")` then store → build client with the token → `info()` and
    verify `protocol_version`. On any failure: close what was opened and raise `TunnelError`.
  - `async rotate_remote_token(machine, *, token_store, tunnel) -> str`:
    `exec("armar-agentd token rotate")` → persist new token → return it.
- **`transport/manager.py`**: `ConnectionManager.__init__` gains injectable `token_store` and
  `tunnel_factory` (defaults: real keyring store + `AsyncSshTunnel`). `_dial` delegates remote
  dials to `dial_remote`; local UDS stays inline + token-less. Add a `rotateToken(name)` slot.

## Acceptance criteria

- [ ] Remote dial with an **empty** store runs `armar-agentd token print` exactly once, persists
      the token, and builds the client with `Authorization: Bearer <token>`.
- [ ] Remote dial with a **populated** store does **not** exec; it reuses the stored token.
- [ ] Empty/failed `token print` (non-zero exit or blank stdout) → `TunnelError`, **nothing
      persisted**, tunnel closed.
- [ ] Protocol-version mismatch → `TunnelError` after the token step; tunnel closed.
- [ ] `rotate_remote_token` execs `token rotate`, persists the new value, returns it.
- [ ] `SecretTokenStore` falls back to in-memory (no crash) when keyring is unavailable.
- [ ] Token never logged; never sent anywhere except the `Authorization` header; never written to
      `machines.toml`.

## Tests (offline, no Qt / no sshd / no D-Bus)

- `test_secret_token_store.py`: roundtrip + delete via `InMemoryTokenBackend`; `SecretTokenStore`
  fallback when a backend raises on import/instantiation.
- `test_connection.py`: `dial_remote` obtain→persist→reuse; blank/again-failed `token print`
  raises and persists nothing; protocol mismatch raises; `rotate_remote_token` persists + returns.
  Uses a `FakeTunnel` and a fake `AgentClient` (`info()` returns a chosen `AgentInfo`).

## Deviations / follow-ups

- Flatpak runtime needs `keyring` vendored (regenerate `flatpak/python3-deps.*.json`) for Secret
  Service to work inside the sandbox — tracked in P4. Until then the sandbox falls back to
  in-memory (tokens re-fetched via SSH-exec each launch — still correct, just not cached).
- Wiring a rotation button into QML is cosmetic and deferred with the rest of the UI polish (P4).
