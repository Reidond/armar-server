# Sandbox Permissions — finish-args, Portals & Least Privilege

Detailed reference for `SKILL.md`. The sandbox is the whole point of Flatpak; broad
permissions are both a security failure and a Flathub rejection. The guiding rule:
**grant nothing by default, add only what the app provably needs, prefer a portal
over a static hole.**

## The mental model

- `finish-args` set the **runtime** sandbox (what the app may touch when users run it).
- A Flatpak starts with **no** host filesystem, **no** network, **no** device, **no**
  arbitrary D-Bus access. Each `finish-args` entry pokes a specific hole.
- **Portals** (`xdg-desktop-portal`) let an app request access *interactively at
  runtime* (file open/save, screenshots, notifications, etc.) **without any static
  permission** — the user's choice grants the access. Portals are almost always the
  correct alternative to a filesystem/device hole.

## Permission categories

| Flag | Grants | Least-privilege guidance |
|------|--------|--------------------------|
| `--share=network` | outbound/inbound network | Add only if the app talks to the network. Never as a build hack. |
| `--share=ipc` | shared IPC namespace (X11 SHM) | Pair with X11; harmless and expected for GUI apps. |
| `--socket=wayland` | Wayland display | Preferred display socket. |
| `--socket=fallback-x11` | X11 **only if Wayland absent** | Use this, not bare `x11`. Requires `--share=ipc`. |
| `--socket=x11` | X11 always, unconfined | ❌ Avoid — lint `finish-args-x11-without-ipc`; use `fallback-x11`. |
| `--socket=pulseaudio` | audio (PipeWire/Pulse) | Only for apps that play/record audio. |
| `--socket=session-bus` | **entire** session D-Bus | ❌ Far too broad — use specific `--talk-name` instead. |
| `--socket=system-bus` | entire system D-Bus | ❌ Too broad — use `--system-talk-name`. |
| `--socket=ssh-auth` | SSH agent socket | Only if the app uses the user's SSH agent. |
| `--device=dri` | GPU acceleration | Common for Qt/GL apps; safe and narrow. |
| `--device=all` | **all** devices (webcam, etc.) | ❌ Avoid — name specific devices (`dri`, `input`). |
| `--filesystem=host` | entire host FS | ❌ Rejected. |
| `--filesystem=home` | entire `$HOME` | ❌ Rejected (incl. `~/.config`, `~/.cache`, `~/.local`, `~/.themes`). |
| `--filesystem=xdg-documents` | `~/Documents` | Acceptable when justified; add `:ro` if read-only. |
| `--filesystem=xdg-download` | `~/Downloads` | Common, narrow. |
| `--filesystem=xdg-config/<app>:ro` | one app's config | Narrow, fine when needed. |
| `--talk-name=NAME` | call a session-bus service | Narrow D-Bus access — the right tool. |
| `--system-talk-name=NAME` | call a system-bus service | Narrow system D-Bus access. |
| `--own-name=NAME` | own a bus name | For apps exposing their own D-Bus API. |
| `--env=VAR=VALUE` | set an env var in-sandbox | Config only; never secrets. |
| `--persist=DIR` | persist a dir under `~/.var/app/<id>` | For app data; HOME inside sandbox maps here anyway. |

Suffixes on `--filesystem`: `:ro` (read-only), `:create` (create if missing),
`:rw` (default). Always prefer `:ro` when the app only reads.

## The three rejection-grade holes (expanded)

### `--filesystem=home` / `--filesystem=host`
- **Why people reach for it:** "the app needs to read the user's files and this makes
  it just work."
- **What actually happens:** the sandbox is effectively disabled — the app can read
  SSH keys, browser profiles, other apps' data. `flatpak-builder-lint` flags blanket
  home/host and sensitive subpaths; Flathub reviewers reject it.
- **Do instead:** the **FileChooser / OpenURI portal** (the app calls the portal, the
  user picks a file in a host file dialog, the app gets just that file — **no static
  permission required**). If you genuinely need standing access to a known location,
  scope it: `--filesystem=xdg-documents:ro`, `--filesystem=xdg-download`.

### `--talk-name=org.freedesktop.Flatpak`
- **Why people reach for it:** lets the app run host commands via `flatpak-spawn --host`.
- **What actually happens:** **total sandbox escape** — arbitrary host code execution.
  Auto-rejected by Flathub.
- **Do instead:** perform the work inside the sandbox; if it needs a host capability,
  use the proper portal or a narrow D-Bus interface. (`flatpak-spawn` *without*
  `--host`, to spawn sandboxed subprocesses, is fine and needs no special permission.)

### `--socket=x11` without `--share=ipc`
- **Why it seems fine:** "X11 works on my machine."
- **What actually happens:** unconfined X11 access (keylogging risk across apps) and
  broken MIT-SHM; lint error `finish-args-x11-without-ipc`.
- **Do instead:** `--socket=wayland` + `--socket=fallback-x11` + `--share=ipc`.

### Theme / icon / font holes (`--filesystem=~/.themes`, `~/.icons`, bundling host fonts)
- **Why people reach for it:** "the app should match the user's GTK/Qt theme and fonts."
- **What actually happens:** these are rejected — they reach into the user's home (a
  sub-case of the `home` hole) and break the sandbox's isolation/portability. Bundling
  host fonts or themes into the app is also rejected.
- **Do instead:** consume themes and icons through the proper **Flatpak theme
  extensions** (`org.kde.KStyle.*` / `org.gtk.Gtk3theme.*`, installed automatically and
  exposed to the sandbox by Flatpak), and rely on the runtime's fonts plus the
  **Settings portal** for the user's appearance preferences. Don't open a filesystem
  hole to pick up host theming.

## Common portals (use instead of holes)

| Need | Portal | Static permission needed? |
|------|--------|---------------------------|
| Open/save a file | FileChooser (`org.freedesktop.portal.FileChooser`) | **None** |
| Open a URI / file with default app | OpenURI | **None** |
| Desktop notifications | Notification | None (or `--talk-name=org.freedesktop.Notifications` for the legacy API) |
| Screenshot / screencast | Screenshot / ScreenCast | None |
| Autostart / background | Background | None |
| Settings (dark mode, accent) | Settings | None |
| Inhibit sleep, set wallpaper, print, etc. | respective portals | None |

Toolkits wire these automatically: **Qt6 / KDE Frameworks and GTK route their native
file dialogs and notifications through portals when run inside Flatpak** — so a Qt
app using `QFileDialog` gets the host file picker with **zero** filesystem args. Don't
add `--filesystem=home` to "make the file dialog work"; it already works via the portal.

## Picking the minimal set — procedure

1. **Start from the baseline:** `--share=ipc --socket=wayland --socket=fallback-x11`
   (+ `--device=dri` for GL/Qt). This runs a GUI app.
2. **Add per proven need**, each justified:
   - Network calls → `--share=network`.
   - Audio → `--socket=pulseaudio`.
   - A specific service → `--talk-name=<exact.bus.name>` (never `--socket=session-bus`).
   - A known data dir the app reads without a dialog → narrowest `--filesystem=xdg-*`,
     `:ro` if possible.
3. **Prefer a portal** for files, notifications, screenshots, settings — drop the
   corresponding `--filesystem`/`--socket` hole.
4. **Lint to confirm:**
   `flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest <app-id>.yaml`
   and fix every reported `finish-args-*` warning before submitting.

## Good vs bad (calibration)

```yaml
# ❌ BAD — disables the sandbox; multiple named rejections
finish-args:
  - --filesystem=home                      # whole home exposed
  - --socket=x11                           # unconfined X11, no ipc
  - --socket=session-bus                   # entire session D-Bus
  - --talk-name=org.freedesktop.Flatpak    # sandbox escape
  - --device=all                           # every device
  - --share=network                        # added "just in case"
```

```yaml
# ✅ GOOD — least privilege; files via portal, one specific service
finish-args:
  - --share=ipc
  - --socket=wayland
  - --socket=fallback-x11
  - --device=dri
  - --talk-name=org.freedesktop.Notifications   # only the service it uses
  # files handled by the FileChooser portal — no --filesystem needed
  # network omitted — this app makes no network calls
```

## Sources to verify against (author-time)

- Sandbox permissions reference: https://docs.flatpak.org/en/latest/sandbox-permissions.html
- Portals overview: https://docs.flatpak.org/en/latest/desktop-integration.html and
  https://flatpak.github.io/xdg-desktop-portal/
- flatpak-builder-lint rules (`exceptions.json`): https://github.com/flathub-infra/flatpak-builder-lint
- `finish-args-x11-without-ipc` explanation:
  https://discourse.flathub.org/t/what-does-finish-args-x11-without-ipc-mean-and-how-do-you-fix-it/3279
