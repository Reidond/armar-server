# Manifest Reference — Schema, Modules, Sources, Offline Dependencies

Detailed reference for `SKILL.md`. Covers the manifest schema, module build systems,
source types, SDK extensions, BaseApps, a complete Python/Qt skeleton, and the
offline Python-dependency workflow (the single most common agent failure).

## Manifest format: YAML or JSON

Both are 1:1 equivalent — pick one for the top-level manifest. YAML is more readable
and supports comments; the KDE project conventionally uses JSON. A `modules:` entry
can `include` a `.json` file regardless of the top-level format, which is how
generated dependency modules are pulled in.

Top-level keys (most-used):

```yaml
id: org.example.App              # reverse-DNS app ID; must match .metainfo.xml <id>
runtime: org.kde.Platform
runtime-version: '6.9'           # branch string — verify newest non-EOL at author time
sdk: org.kde.Sdk
base: io.qt.PySide.BaseApp       # optional: prebuilt layer (PySide6 here)
base-version: '6.9'              # must align with the runtime's Qt/version line
command: example-app             # binary/script run by `flatpak run`
sdk-extensions:                  # optional: extra compilers for native deps
  - org.freedesktop.Sdk.Extension.rust-stable
finish-args: [...]               # sandbox permissions — see sandbox-permissions.md
cleanup:                         # globs removed from the final app to slim it
  - '/include'
  - '/lib/pkgconfig'
  - '*.a'
  - '*.la'
modules: [...]                   # ordered build units (see below)
```

`finish-args` define the runtime sandbox; `build-options`/`build-args` affect the
**build** environment. Never paper over a build problem with `--share=network` in
`build-args` — that is exactly what Flathub CI forbids.

## Modules

`modules:` is an ordered list; each builds and installs into the `/app` prefix that
later modules and the final app see. A module:

```yaml
- name: example-app
  buildsystem: simple            # autotools(default)|cmake|cmake-ninja|meson|qmake|simple
  build-options:
    build-args: []               # NO --share=network for Flathub
    append-path: /usr/lib/sdk/rust-stable/bin   # expose an SDK extension's tools
    env:
      CARGO_HOME: /run/build/example-app/cargo
  build-commands:                # required for buildsystem: simple
    - pip3 install --prefix=/app --no-build-isolation --no-deps .
  sources:
    - type: archive
      url: https://example.org/releases/app-1.2.3.tar.xz
      sha256: <64-hex>
  cleanup:
    - '*.pyc'
```

- **`buildsystem: simple`** is what Python apps use — you supply explicit
  `build-commands`. `cmake-ninja`/`meson`/`qmake` autogenerate configure+build+install.
- Module order matters: build dependency libraries (each its own module) **before**
  the app module that links them.
- Per-module `cleanup:` removes build-only artifacts; top-level `cleanup:` runs last.
- A module can `name: …` + only `sources: [{ type: shell }]` for tiny steps, but
  prefer real source entries.

## Source types

| `type` | Pins with | Use for |
|--------|-----------|---------|
| `archive` | `sha256` (+ `url`) | release tarballs (`.tar.gz/.xz/.zst`, `.zip`) |
| `file` | `sha256` (+ `url` or `path`) | single files, wheels, patches kept locally |
| `git` | `commit:` (a full SHA — **not** `branch`/`tag` alone) | building from a VCS checkout |
| `dir` | — | local dir (dev only; not for Flathub) |
| `patch` | `path:` | apply a patch file to the prior source |
| `script` / `shell` | — | generate a file/run a command (offline only) |

Rules that keep CI green:
- **Always pin.** `archive`/`file` → `sha256`; `git` → a full 40-char `commit`. A
  bare `tag:`/`branch:` is non-reproducible and rejected.
- Compute a hash with `sha256sum <file>` (or `flatpak-builder` will print a mismatch).
- Multiple `sources` in one module are applied in order (e.g. archive then patches).

## SDK extensions (native build deps)

When a dependency needs a compiler not in the base SDK:

```yaml
sdk-extensions:
  - org.freedesktop.Sdk.Extension.rust-stable    # Rust — cryptography, cffi, pydantic-core, etc.
  - org.freedesktop.Sdk.Extension.llvm18
modules:
  - name: …
    build-options:
      append-path: /usr/lib/sdk/rust-stable/bin   # the extension installs under /usr/lib/sdk/<name>
      env: { CARGO_NET_OFFLINE: '1' }
```

Common trigger: a Python app depending on `cryptography` (via `asyncssh`, `paramiko`,
etc.) or `pydantic` v2 (`pydantic-core` is Rust). These have **no pure-Python wheel**,
so the offline build must compile them → you need `rust-stable` and the crates
vendored as pinned sources (cargo offline). Prefer a prebuilt wheel source when one
exists for the runtime's architecture to avoid compiling Rust at all.

## BaseApp (PySide6 / Qt-for-Python)

A BaseApp is a prebuilt stack layered via `base:`/`base-version:`. For PySide6 the
canonical one is **`io.qt.PySide.BaseApp`** — it ships a ready PySide6 so you don't
rebuild Qt bindings (which is slow and fragile). Match `base-version` to the runtime's
Qt branch and run its cleanup:

```yaml
runtime: org.kde.Platform
runtime-version: '6.9'
sdk: org.kde.Sdk
base: io.qt.PySide.BaseApp
base-version: '6.9'
# BaseApps usually ship a cleanup script you must invoke; per the KDE guide:
build-options:
  prepend-path: /app/bin
cleanup-commands:
  - /app/cleanup-BaseApp.sh
```

(Confirm the exact cleanup-script path and `base-version` against the current KDE
"Publishing your Python app as a Flatpak" guide and the `io.qt.PySide.BaseApp` repo.)

## Offline Python dependencies

This is where agents most often break a manifest. **You cannot `pip install <pkg>`
during the build** — there is no network. You must convert your dependency set into
pinned `source` entries ahead of time.

### Step 1 — generate pinned sources

Use a generator **inside the matching runtime** so wheel ABIs/architectures resolve
the way the build will see them:

```bash
# flatpak-pip-generator (from flatpak/flatpak-builder-tools):
python3 flatpak-pip-generator --runtime=org.kde.Sdk//6.9 --requirements-file=requirements.txt \
  --output python3-deps
# → produces python3-deps.json: a module with one pinned (url+sha256) source per wheel/sdist.

# Alternative — req2flatpak (resolves directly from PyPI, good for pure-Python sets):
req2flatpak --requirements requirements.txt --target-platforms 312-x86_64 --outfile python3-deps.json
```

Pin your requirements to exact versions first so the generated hashes are
deterministic — prefer `uv pip compile`/`uv export` (or a `uv.lock`); `pip freeze` is
a fallback when uv isn't available.

### Step 2 — include the generated module and install offline

```yaml
modules:
  - python3-deps.json            # the generated module: all deps as pinned sources
  - name: example-app
    buildsystem: simple
    build-commands:
      # --no-build-isolation: don't fetch build backends (offline);
      # --no-deps: deps already installed by python3-deps.json above
      - pip3 install --prefix=/app --no-build-isolation --no-deps .
    sources:
      - type: archive
        url: https://example.org/releases/app-1.2.3.tar.xz
        sha256: <64-hex>
```

Notes:
- `--no-build-isolation` is essential: build isolation tries to **download** the build
  backend (hatchling/setuptools/poetry-core) → fails offline. Add the backend itself
  as a dependency source if it isn't already in the runtime.
- A **dynamic VCS version** (e.g. hatchling + `uv-dynamic-versioning`) has no git tags
  in a release tarball → the build can't compute a version. Supply a concrete version
  via a `fallback-version`/`SETUPTOOLS_SCM_PRETEND_VERSION`-style env, or build from a
  `git` source pinned to the release `commit` so tag metadata is present.
- Ship QML/data files: they must land under `/app`. A `pip install` only copies data
  files that the wheel actually declares (package-data/`include`), so verify the wheel
  contains them, or copy them explicitly in `build-commands`
  (`install -Dm644 … /app/share/…`).

## Complete skeleton: Python + Qt (PySide6) + QML app

```yaml
id: org.example.App
runtime: org.kde.Platform
runtime-version: '6.9'            # verify newest non-EOL branch at author time
sdk: org.kde.Sdk
base: io.qt.PySide.BaseApp
base-version: '6.9'
command: example-app

finish-args:
  - --share=ipc
  - --socket=wayland
  - --socket=fallback-x11
  - --device=dri
  # add ONLY what the app proves it needs, e.g.:
  # - --share=network                       # only if the app makes network calls
  # - --talk-name=org.freedesktop.Notifications

cleanup:
  - /include
  - /lib/pkgconfig
  - '*.a'
  - '*.la'
cleanup-commands:
  - /app/cleanup-BaseApp.sh

modules:
  # 1) third-party Python deps as pinned sources (generated; offline)
  - python3-deps.json

  # 2) the app itself, built from a pinned release archive
  - name: example-app
    buildsystem: simple
    build-commands:
      - pip3 install --prefix=/app --no-build-isolation --no-deps .
      - install -Dm644 org.example.App.desktop /app/share/applications/org.example.App.desktop
      - install -Dm644 org.example.App.metainfo.xml /app/share/metainfo/org.example.App.metainfo.xml
      - install -Dm644 org.example.App.svg /app/share/icons/hicolor/scalable/apps/org.example.App.svg
    sources:
      - type: archive
        url: https://example.org/releases/app-1.2.3.tar.xz
        sha256: '0000000000000000000000000000000000000000000000000000000000000000'
        x-checker-data:
          type: pypi            # or anitya/git/html — see flathub-publishing.md
          name: example-app
```

Build, lint, and run it with the loop in `SKILL.md`. The `.desktop`, `.metainfo.xml`,
icon, app-ID, and `x-checker-data` requirements are detailed in
[flathub-publishing.md](flathub-publishing.md).

## Sources to verify against (author-time)

- Flatpak manifest reference: https://docs.flatpak.org/en/latest/manifests.html
- flatpak-builder: https://docs.flatpak.org/en/latest/flatpak-builder.html
- Python apps: https://docs.flatpak.org/en/latest/python.html
- Available runtimes / SDK extensions: https://docs.flatpak.org/en/latest/available-runtimes.html
- flatpak-builder-tools (`flatpak-pip-generator`): https://github.com/flatpak/flatpak-builder-tools
- req2flatpak: https://github.com/johannesjh/req2flatpak
- KDE — Publishing your Python app as a Flatpak: https://develop.kde.org/docs/getting-started/python/python-flatpak/
