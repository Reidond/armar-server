# armar-server

Run a **modded Arma Reforger dedicated server** with a single set of commands. You give it Arma
Workshop URLs; it parses each mod, resolves the full dependency tree, pins versions, generates the
Reforger JSON config, and runs the server in a container.

```
workshop URLs  ──►  resolve (parse + deps + pin)  ──►  armar.lock
                                                          │
server.toml  ─────────────────────────────────────────►  config  ──►  server-config.json
                                                                          │
docker image + SteamCMD (app 1874900)  ──►  install  ──►  run / up  ──►  Reforger server
```

- **Mods from URLs** — paste `https://reforger.armaplatform.com/workshop/<id>`; dependencies are
  resolved automatically and pinned to a lockfile for reproducible runs.
- **Containerized** — the server runs in an Ubuntu-based container, so you don't fight Fedora's
  glibc/libssl quirks. Rootless **Podman** by default; **Docker** also supported.
- **Full lifecycle** — build image → install/update server (SteamCMD) → render config → run.
- **Both run modes** — foreground (`armar run`) for testing, detached + systemd for production.

> Built strictly on [uv](https://docs.astral.sh/uv/). All Python operations go through uv.

## Requirements

- Linux with **Podman** (recommended, rootless) or **Docker**.
- **uv** (`curl -LsSf https://astral.sh/uv/install.sh | sh`). uv manages the Python toolchain.
- Disk: ~5 GB for the base server, 15–25 GB once mods download.
- Open UDP ports (defaults): **2001** (game, required), **17777** (A2S query), **19999** (RCON, optional).

## Install

```bash
git clone <this repo> && cd armar-server
uv sync                 # creates the venv and installs everything from uv.lock
uv run armar --help
```

Optionally install the `armar` command globally: `uv tool install ./packages/armar-cli`

## Quickstart

```bash
uv run armar init                                                  # write server.toml
uv run armar mods add https://reforger.armaplatform.com/workshop/6922BD179EEDD0D2
uv run armar resolve                                              # fetch + resolve deps -> armar.lock
uv run armar scenarios                                            # list scenario ids from your mods
# edit server.toml: set scenario_id (and password/admins as desired)
uv run armar config                                              # render data/config/server-config.json
uv run armar build                                               # build the container image (once)
uv run armar install                                            # SteamCMD installs the server (app 1874900)
uv run armar run                                                # foreground; Ctrl-C to stop
# ...or detached:
uv run armar up      &&  uv run armar logs -f
```

`uv run armar doctor` checks everything is ready (runtime, config, lock, scenario, server install).

## Commands

| Command | Description |
|---|---|
| `armar init` | Create a starter `server.toml`. |
| `armar mods add <url\|id>…` | Add mods (Workshop URL or hex id) to `server.toml`. |
| `armar mods remove <url\|id>…` / `armar mods list` | Manage the mod list. |
| `armar resolve` | Fetch metadata, resolve dependencies, pin versions → `armar.lock`. |
| `armar scenarios` | List scenario ids advertised by your mods (copy one into `scenario_id`). |
| `armar config` | Render `data/config/server-config.json` from `server.toml` + `armar.lock`. |
| `armar build` | Build the container image (`docker/`). |
| `armar install` / `armar update` | Install/update the server via SteamCMD into `data/server`. |
| `armar run` | Render config + run the server in the foreground. |
| `armar up` / `stop` / `status` / `logs [-f]` | Manage the detached server container. |
| `armar service install [--print]` | Generate a systemd unit (Podman Quadlet or Docker `.service`). |
| `armar doctor` | Check environment readiness. |

## Configuration

### `server.toml` (you edit this)

Friendly settings under a `[server]` table. Highlights:

| Key | Meaning |
|---|---|
| `name` | Server name shown in the browser. |
| `scenario_id` | The single scenario to run, e.g. `{ECC61978EDCC2B5A}Missions/23_Campaign.conf`. Reforger runs **one** scenario (no rotation). Find ids with `armar scenarios`. |
| `mods` | Workshop URLs or hex ids. Managed by `armar mods add/remove`. |
| `password` / `admin_password` / `admins` | Access control (admin password: no spaces). |
| `max_players`, `visible`, `cross_platform`, `battleye` | Common game options. |
| `bind_port`, `public_address`, `public_port`, `a2s_port` | Networking (leave `public_address` empty in host-network mode). |
| `rcon_enabled`, `rcon_password`, `rcon_port` | Optional RCON (password ≥ 3 chars, no spaces). |
| `max_fps` | Frame cap (60 recommended by Bohemia). |
| `[server.game_properties]`, `[server.operating]` | Advanced passthrough merged verbatim into the JSON. |

### `armar.lock` (generated)

Produced by `armar resolve`: the flattened, deduplicated, version-pinned mod set (your mods + all
dependencies). Re-run `armar resolve` to bump to the latest versions.

### `server-config.json` (generated)

The actual Reforger config passed via `-config`. Produced by `armar config`; lives under
`data/config/`. `fastValidation` is forced on for public play.

## How mod resolution works

The Workshop site (`reforger.armaplatform.com`) embeds full mod metadata in a `__NEXT_DATA__` JSON
blob in the page — no API key, no headless browser. `armar resolve` fetches each mod once (cached),
reads its dependencies (recursively, with a cycle guard), and pins each mod to its current latest
version. Example: `6922BD179EEDD0D2` (ARMST PLATFORM) resolves to 1 direct mod + 22 dependencies.

## Container & networking

The server runs in a container built from `docker/Dockerfile` (Ubuntu 22.04 + SteamCMD + required
libs). The server **binary, downloaded mods, and config live on host volumes** (`data/server`,
`data/profile`, `data/config`), so updates and restarts don't re-download everything.

- **Networking:** defaults to `--network=host`, which is simplest and avoids the known issue where a
  bridged container registers its own IP and clients can't connect. Set `ARMAR_NETWORK_MODE=bridge`
  to publish UDP ports instead; in that mode `public_address` is auto-detected (your LAN IP) if empty.
- **Fedora/Podman:** volume mounts are SELinux-relabeled (`:Z`) and the container user is mapped to
  your host user (`--userns=keep-id`) automatically.
- **Runtime/image overrides:** `ARMAR_RUNTIME` (`podman`|`docker`), `ARMAR_IMAGE`, `ARMAR_DATA_DIR`,
  `ARMAR_CONFIG_FILE`, `ARMAR_LOCK_FILE`, `ARMAR_NETWORK_MODE` (see `packages/armar-core/src/armar_server/config/settings.py`).

## Running as a service

```bash
uv run armar service install        # Podman -> ~/.config/containers/systemd/armar.container (Quadlet)
                                    # Docker -> ~/.config/systemd/user/armar.service
systemctl --user daemon-reload
systemctl --user start armar        # (Quadlet) — auto-restarts on failure
```

Use `armar service install --print` to preview the unit without writing it.

## Troubleshooting

- **`curl_easy_perform, code: 23` while downloading mods** — the temp dir isn't writable; armar already
  passes `-addonTempDir /addons-tmp`. Ensure the container user can write there (rootless Podman maps it).
- **Players can't connect from outside / wrong IP registered** — use host networking (default), or set
  `public_address` to your reachable IP in bridged mode and forward the UDP ports on your router.
- **Server won't start with empty `scenario_id`** — run `armar scenarios` and set one.
- **libssl errors on an older base image** — the image targets Ubuntu 22.04 (libssl3); if a future
  Reforger build needs `libssl1.1`, add it in `docker/Dockerfile`.

## Development

```bash
uv run ruff check . && uv run ruff format --check .
uv run basedpyright
uv run pytest
```

The test suite is fully offline: the workshop client is faked at its Protocol boundary (or mocked with
`pytest-httpx`) and container invocations are asserted as argv — no network or containers required.

## References

Authoritative Arma Reforger docs are bundled in `docs/` (BI Community Wiki: *Server Config*,
*Server Hosting*, *Startup Parameters*). Always check these before changing the config schema,
startup parameters, or SteamCMD usage — they change between game versions.

---

This repo also carries an AI-development infrastructure layer (`AGENTS.md`, `CLAUDE.md`,
`.claude/skills/`, `.ai/`) used by AI coding assistants. See `AGENTS.md` for project conventions.
