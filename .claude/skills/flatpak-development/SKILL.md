---
name: flatpak-development
description: >
  Expert guidance for packaging desktop apps as Flatpaks: authoring manifests
  (YAML/JSON modules, sources with sha256, build systems), building/running/debugging
  with org.flatpak.Builder + flatpak-builder-lint, configuring the sandbox with
  least-privilege finish-args and XDG portals, packaging Python/Qt/KDE apps
  (org.kde.Platform, PySide6 BaseApp, offline pip dependency pinning), and publishing
  to Flathub (MetaInfo/AppStream, desktop files, app-ID rules, the new-pr submission
  pipeline, x-checker-data). Auto-loads when working on Flatpak manifests, sandbox
  permissions, or Flathub submissions.
  Keywords: flatpak, flatpak-builder, org.flatpak.Builder, flatpak-builder-lint,
  flathub, manifest, finish-args, sandbox, portal, xdg-desktop-portal, metainfo,
  appstream, appstreamcli, runtime, SDK, BaseApp, org.kde.Platform, org.gnome.Platform,
  org.freedesktop.Platform, flatpak-pip-generator, req2flatpak, x-checker-data,
  PySide6, Qt, KDE, desktop packaging, .metainfo.xml, .desktop.
user-invocable: false
metadata:
  type: reference
---

# Flatpak Development — Packaging, Sandboxing & Flathub Publishing

## Role

Background knowledge for authoring, building, sandboxing, and publishing Flatpaks
correctly — especially Python/Qt/KDE desktop apps. The bar is **a manifest that
passes Flathub CI on the first try**, not one that merely builds on your machine.

Apply this whenever you touch a Flatpak manifest (`*.yaml`/`*.yml`/`*.json` with
`app-id`/`runtime`/`modules`), `*.metainfo.xml`, a `*.desktop` file, `finish-args`,
or anything under a `flathub/` submission.

## ⚠️ Two failure modes dominate agent-authored manifests

Read these first — almost every broken Flatpak an agent produces is one of these.

### 1. Network during build → build fails in CI
**Flathub builds run with NO network access.** A manifest that `pip install`s,
`npm install`s, `git clone`s, or curls during `build-commands` works locally (your
cache has the bits) and **fails the moment Flathub's sandboxed builder runs it.**

Every input must be a declared `source` with a pinned **`sha256`** (or `git` +
`commit:`). For Python, pre-resolve deps into pinned sources with
`flatpak-pip-generator`/`req2flatpak`, then install `--no-build-isolation --no-deps`.
See [references/manifest-reference.md](references/manifest-reference.md#offline-python-dependencies).

### 2. Sandbox holes → Flathub rejection
Broad permissions defeat the sandbox and are **named rejection reasons**, caught by
`flatpak-builder-lint`. The three worst, all auto-rejected:

| ❌ Never | Why it's rejected | ✅ Instead |
|---------|-------------------|-----------|
| `--filesystem=home` / `--filesystem=host` | exposes the user's whole home / OS | XDG **portals** (no perm needed) or narrow `--filesystem=xdg-documents:ro` |
| `--talk-name=org.freedesktop.Flatpak` | enables `flatpak-spawn --host` = **full sandbox escape** | do the work in-sandbox, or use a real portal/D-Bus interface |
| `--socket=x11` (alone) | unconfined X11, no SHM; lint error `finish-args-x11-without-ipc` | `--socket=wayland` + `--socket=fallback-x11` + `--share=ipc` |

Default to the **least-privilege baseline** and add only what the app provably needs:
```
finish-args:
  - --share=ipc
  - --socket=wayland
  - --socket=fallback-x11
  - --device=dri          # GPU; omit if not needed
```
Full permission reference + portal mapping: [references/sandbox-permissions.md](references/sandbox-permissions.md).

## The build → lint → run loop (use this, every time)

Target **`org.flatpak.Builder`** (the Flatpak'd builder), **not** the distro
`flatpak-builder` package. It bundles `flatpak-builder-lint` and is what Flathub CI
runs — so passing locally means passing in review. Build and lint as one habit:

```bash
flatpak install -y flathub org.flatpak.Builder

# build + install to the user installation, creating an ostree repo for the repo lint:
flatpak run org.flatpak.Builder --force-clean --user --install \
  --install-deps-from=flathub --ccache \
  --mirror-screenshots-url=https://dl.flathub.org/media/ \
  --repo=repo builddir <app-id>.yaml

# lint EXACTLY as Flathub CI does — both checks must pass:
flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest <app-id>.yaml
flatpak run --command=flatpak-builder-lint org.flatpak.Builder repo repo

flatpak run <app-id>      # smoke-test the actual sandboxed app
```

- `--force-clean` wipes `builddir`; `--ccache` caches C/C++ compiles across runs.
- The `repo` lint needs an ostree repo (hence `--repo=repo`); the `manifest` and
  `repo` checks **both** gate every Flathub build. (A `builddir` check —
  `flatpak-builder-lint builddir builddir` — also exists if you want to lint before
  exporting a repo.)
- Debugging a build: `flatpak run --command=sh org.flatpak.Builder` to poke inside,
  or `flatpak-builder --build-shell=<module> …` to drop into a module's build env.
  Inspect the installed tree at `~/.local/share/flatpak/app/<app-id>/`.

## Runtime / SDK selection (decision tree)

Pick the runtime, then **look up the newest non-EOL branch at author time** — an
**EOL runtime is a hard Flathub rejection**, and branch numbers churn. Never emit a
memorized version; verify against `docs.flatpak.org/.../available-runtimes.html` and
the Flathub requirements page. (As a rough mid-2026 anchor only: freedesktop's current
line is `25.08`, KDE tracks Qt6 `6.x`, GNOME its yearly branch — treat these as
sanity-check defaults to confirm, not values to paste.)

```
Is it a Qt / KDE / QML / PySide6 app?
  YES → runtime: org.kde.Platform   sdk: org.kde.Sdk   (Qt6 + KDE Frameworks)
        PySide6?  → also base: io.qt.PySide.BaseApp  (+ base-version, + cleanup)
  NO ↓
Is it a GTK / libadwaita (GNOME) app?
  YES → runtime: org.gnome.Platform  sdk: org.gnome.Sdk
  NO ↓
Anything else (CLI, custom toolkit, SDL, Electron-ish)?
  → runtime: org.freedesktop.Platform  sdk: org.freedesktop.Sdk
```

- **`runtime-version`** is the branch string (e.g. KDE `6.9`, freedesktop `25.08`).
  freedesktop releases every **August**, ~2-year support; KDE tracks Qt6 minor
  branches; GNOME tracks its ~yearly calendar. Confirm the current stable branch.
- **BaseApp** (`base:` / `base-version:`) stacks a prebuilt layer (e.g. a ready
  PySide6) between runtime and app so you don't rebuild Qt bindings. `base-version`
  must match the runtime's Qt/version line.
- **SDK extensions** for native build deps: `org.freedesktop.Sdk.Extension.rust-stable`
  (needed for `cryptography`/`cffi`/Rust wheels), `.llvm*`, `.node*`, `.golang` —
  add to `sdk-extensions:` and prepend to `PATH` via `build-options.append-path`.

Details, full skeleton manifest, and the offline-dependency workflow:
[references/manifest-reference.md](references/manifest-reference.md).

## Flathub publishing is a gated pipeline

Don't treat "it builds" as "it's done." Flathub listing requires more, and several
items silently fail the build/listing if wrong.

- **MetaInfo is a hard gate.** Ship `<app-id>.metainfo.xml` in `/app/share/metainfo/`
  (the old `.appdata.xml` name is legacy). Required: `id` (== app ID, == `.desktop`
  basename), `name`, `summary`, `metadata_license` (e.g. `CC0-1.0`), `project_license`
  (SPDX), `<developer id><name>`, `<description>`, `<launchable type="desktop-id">`,
  `screenshots`, `content_rating type="oars-1.1"`, and `releases`. Validate with
  `flatpak run --command=flatpak-builder-lint org.flatpak.Builder appstream <id>.metainfo.xml`
  (and `appstreamcli validate`).
- **App ID rules:** reverse-DNS, 3–5 components, `[A-Za-z0-9_]` only (dash allowed
  only in the last component). Code-host prefixes are mandatory and must reflect real
  ownership: `io.github.<user>.<App>`, `io.gitlab.<user>.<App>`, `page.codeberg.<user>.<App>`.
- **Submission:** fork `flathub/flathub`, add your manifest, open a PR against the
  **`new-pr`** branch (not `master`); comment `bot, build` to trigger a test build;
  on merge you get your own repo. **Use `--user` installs while testing.**
- **Ongoing maintenance:** attach `x-checker-data` to sources (checker types `pypi`,
  `anitya`, `git`, `html`, `json`…) so `flatpak-external-data-checker` opens update PRs.

Full MetaInfo template, `.desktop` requirements, app-ID rules, submission steps, and
`x-checker-data` examples: [references/flathub-publishing.md](references/flathub-publishing.md).

## ⚠️ Flathub policy: AI-generated content is banned for new submissions

Flathub's requirements (2026) **reject new applications containing AI-generated or
AI-assisted code, documentation, or any other content** — and this explicitly extends
to the **Flatpak manifest, build scripts, patches, and the submission PR itself**, plus
a ban on LLM-generated review/PR comments. The **only carve-out is "mature,
well-maintained projects."** So this is *not* merely a "don't click submit yourself"
rule — agent-authored packaging is itself the prohibited "AI-assisted code" for a
brand-new Flathub app.

What this means when you (an agent) produce Flatpak packaging:

- **For a new Flathub submission:** AI-authored manifests/MetaInfo/patches are
  disallowed unless the project qualifies for the maturity exception. A human clicking
  "submit" does **not** make AI-authored packaging compliant. The human maintainer must
  genuinely **author and own** the packaging; treat your output as a learning reference
  or starting point they rewrite, not a submittable artifact. **Never auto-open a PR to
  `flathub/flathub`.**
- **Always flag this policy to the user explicitly** before they consider Flathub
  distribution, so they can judge the maturity exception and authorship.
- **This does not restrict local/private Flatpak builds or non-Flathub distribution** —
  those are unaffected, and the rest of this skill applies fully.

## Verify-at-author-time checklist

This domain churns; confirm against current docs before finalizing rather than
trusting memory:

- [ ] **Runtime branch** is the newest non-EOL one (KDE/GNOME/freedesktop).
- [ ] **Build + lint** with `org.flatpak.Builder`; both `manifest` and `repo` checks pass.
- [ ] **No network** in build (no `pip install <pkg>`/`git clone`/`--share=network`);
      all sources pinned with `sha256`/`commit`.
- [ ] **finish-args** are least-privilege; no `home`/`host`/`org.freedesktop.Flatpak`/bare `x11`.
- [ ] **MetaInfo** present, correctly named, passes `appstream` lint; app ID matches
      `.metainfo.xml` `<id>` and `.desktop` basename.
- [ ] **App ID** uses a valid code-host prefix reflecting real ownership.
- [ ] **AI-authorship** caveat surfaced if targeting Flathub.

## Reference files

- [references/manifest-reference.md](references/manifest-reference.md) — manifest schema,
  module build systems, sources, SDK extensions, BaseApp, a complete Python/Qt skeleton
  manifest, and the offline pip-dependency workflow (`flatpak-pip-generator`/`req2flatpak`).
- [references/sandbox-permissions.md](references/sandbox-permissions.md) — every
  `finish-args` permission, the portal-vs-hole mapping, good/bad tables, and how to
  pick the minimal set.
- [references/flathub-publishing.md](references/flathub-publishing.md) — full MetaInfo
  template + required fields, `.desktop` file, app-ID rules, the `new-pr` submission
  pipeline, `flathub.json`, and `x-checker-data` for automated updates.
