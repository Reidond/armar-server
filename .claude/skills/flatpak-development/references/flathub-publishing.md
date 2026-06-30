# Flathub Publishing — MetaInfo, Desktop Files, App IDs, Submission

Detailed reference for `SKILL.md`. "It builds" is not "it's publishable." Flathub
listing has hard gates that silently fail a build or a listing if wrong. Verify every
rule against current docs (`docs.flathub.org`) — policies and lint rules churn.

> **Policy reminder (see SKILL.md):** Flathub's 2026 requirements **reject new
> submissions containing AI-generated/AI-assisted content — including the manifest,
> build scripts, patches, and the submission PR** — with the only carve-out being
> "mature, well-maintained projects." A human clicking "submit" does not launder
> AI-authored packaging into compliance; the human maintainer must author and own it.
> Never open a `flathub/flathub` PR automatically. (Local/private and non-Flathub
> builds are unaffected.)

## App ID rules

The app ID is reverse-DNS and used everywhere (manifest `id`, `.metainfo.xml` `<id>`,
`.desktop` basename, D-Bus name, install path). Rules:

- 3–5 components, total ≤ 255 chars; components use `[A-Za-z0-9_]` only; a dash is
  allowed **only in the last component**; a component can't start with a digit.
- The prefix must reflect **real ownership** of the domain/account. Code-host prefixes
  are mandatory when you don't own a domain:
  - GitHub → `io.github.<user>.<App>`
  - GitLab → `io.gitlab.<user>.<App>`
  - Codeberg → `page.codeberg.<user>.<App>`
  - Own domain `example.org` → `org.example.App`
- Must match across: manifest `id`, `<id>` in MetaInfo, the `.desktop` filename, the
  icon filename, and `--own-name`/D-Bus usage.

## MetaInfo / AppStream (`<app-id>.metainfo.xml`)

Ship at `/app/share/metainfo/<app-id>.metainfo.xml`. The legacy `.appdata.xml` name
is deprecated — use `.metainfo.xml`. This is a **hard gate**: the `appstream` lint
and `appstreamcli validate` must pass.

Required / expected elements (current AppStream):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>org.example.App</id>                          <!-- == app ID == .desktop basename -->
  <name>Example App</name>
  <summary>One-line, no trailing period, &lt; ~35 chars</summary>

  <metadata_license>CC0-1.0</metadata_license>       <!-- license of THIS metadata -->
  <project_license>GPL-3.0-or-later</project_license><!-- SPDX id of the app's license -->

  <!-- Modern form: <developer id> with a nested <name>, NOT bare <developer_name> -->
  <developer id="org.example">
    <name>Example Developer</name>
  </developer>

  <description>
    <p>A full paragraph describing what the app does. Plain prose; no marketing fluff,
       no feature-bragging, no "the best".</p>
    <p>A second paragraph is fine. Lists use &lt;ul&gt;&lt;li&gt;.</p>
  </description>

  <launchable type="desktop-id">org.example.App.desktop</launchable>

  <screenshots>
    <screenshot type="default">
      <image>https://example.org/screenshots/main.png</image>
      <caption>The main window</caption>
    </screenshot>
  </screenshots>

  <!-- OARS content rating is REQUIRED; "none" of every category is still an explicit tag -->
  <content_rating type="oars-1.1" />

  <!-- At least one release entry is required -->
  <releases>
    <release version="1.2.3" date="2026-01-15">
      <description><p>Bug fixes and a new export feature.</p></description>
    </release>
  </releases>

  <!-- Recommended branding (light/dark accent colors) -->
  <branding>
    <color type="primary" scheme_preference="light">#3584e4</color>
    <color type="primary" scheme_preference="dark">#1a5fb4</color>
  </branding>

  <url type="homepage">https://example.org</url>
  <url type="bugtracker">https://github.com/example/app/issues</url>
  <url type="vcs-browser">https://github.com/example/app</url>
</component>
```

Validate (both, as CI does):

```bash
flatpak run --command=flatpak-builder-lint org.flatpak.Builder appstream org.example.App.metainfo.xml
appstreamcli validate org.example.App.metainfo.xml
```

Common validation failures: wrong filename/path; bare `<developer_name>` instead of
`<developer id><name>`; missing `content_rating`, `releases`, or `launchable`;
summary with a trailing period or marketing language; screenshot URLs that aren't
reachable (Flathub mirrors them via `--mirror-screenshots-url`, used in the build loop).

## Desktop entry (`<app-id>.desktop`)

Ship at `/app/share/applications/<app-id>.desktop`. Filename basename must equal the
app ID and the MetaInfo `<launchable>`.

```ini
[Desktop Entry]
Type=Application
Name=Example App
Comment=Short description, matches the MetaInfo summary
Exec=example-app
Icon=org.example.App                 # basename of the installed icon, == app ID
Categories=Utility;                  # valid freedesktop categories, trailing ;
Terminal=false
```

Icons go to `/app/share/icons/hicolor/<size>/apps/<app-id>.{png,svg}` (provide a
scalable SVG and/or a 256×256 PNG). The `Icon=` key uses the app-ID basename, no path
or extension.

## Build → lint → submit pipeline

1. **Build + lint locally** with the `org.flatpak.Builder` loop in `SKILL.md`; both
   the `manifest` and `repo` lint checks must pass clean.
2. **Fork `flathub/flathub`** and create a branch. Put the manifest (named
   `<app-id>.yaml`/`.json`) plus any files it references locally (MetaInfo, `.desktop`,
   icons, generated `python3-deps.json`, patches) at the **repo root** — not in a
   subdirectory. A `flathub.json` (optional) also goes at the root. Confirm the exact
   expected file set against the current submission docs before opening the PR.
3. **Open a PR against the `new-pr` branch** (NOT `master`). Submitting against the
   wrong branch is a frequent mistake.
4. **Trigger a test build** by commenting `bot, build` on the PR; the bot builds in the
   same offline sandbox CI uses and reports lint results.
5. **On acceptance/merge**, Flathub creates a dedicated repo for your app
   (`flathub/<app-id>`) that you maintain going forward.
6. Use **`--user` installs** while iterating locally so you don't touch the system
   installation.

### `flathub.json`

Optional per-app build configuration in the app repo (e.g. restricting architectures,
end-of-life rebase metadata, skipping appstream for non-graphical apps). Verify the
current accepted keys against `docs.flathub.org` before adding — the option set
changes; don't copy stale examples.

## Keeping it updated: `x-checker-data`

Attach `x-checker-data` to a `source` so `flatpak-external-data-checker` opens
automated update PRs when a new version appears. Checker `type`s include `pypi`,
`anitya` (release-monitoring.org), `git`, `gnome`, `html`, `json`, `rotating`.

```yaml
# PyPI package — bumps url+sha256 on new releases
sources:
  - type: archive
    url: https://files.pythonhosted.org/.../example_app-1.2.3.tar.gz
    sha256: <hex>
    x-checker-data:
      type: pypi
      name: example-app

# Git tag tracking
  - type: git
    url: https://github.com/example/app.git
    tag: v1.2.3
    commit: <full-sha>
    x-checker-data:
      type: git
      tag-pattern: 'v([\d.]+)'

# Anitya (release-monitoring.org) — for upstreams without a PyPI/git source the checker tracks
  - type: archive
    url: https://example.org/releases/example-1.2.3.tar.xz
    sha256: <hex>
    x-checker-data:
      type: anitya
      project-id: 12345          # the project's release-monitoring.org id
      stable-only: true
      url-template: https://example.org/releases/example-$version.tar.xz
```

## Pre-submission checklist

- [ ] App ID valid (real-ownership prefix, ≤5 components) and identical across
      manifest `id`, `.metainfo.xml` `<id>`, `.desktop` basename, icon basename.
- [ ] `<app-id>.metainfo.xml` present in `/app/share/metainfo/`; passes `appstream`
      lint + `appstreamcli validate`; has `developer`, `content_rating`, `releases`,
      `launchable`, `screenshots`.
- [ ] `<app-id>.desktop` installed with matching `Icon=` and `Exec=`.
- [ ] Icon installed under hicolor (SVG and/or 256×256 PNG).
- [ ] Build is fully offline; all sources pinned (`sha256`/full `commit`).
- [ ] `finish-args` least-privilege; no rejection-grade holes.
- [ ] Runtime branch is current (non-EOL).
- [ ] `manifest` + `repo` lint pass clean with `org.flatpak.Builder`.
- [ ] PR targets `new-pr`; `x-checker-data` added for maintainability.
- [ ] **Human maintainer owns the submission** (AI-authorship policy).

## Sources to verify against (author-time)

- Flathub requirements: https://docs.flathub.org/docs/for-app-authors/requirements
- Submission process: https://docs.flathub.org/docs/for-app-authors/submission
- Linter: https://docs.flathub.org/docs/for-app-authors/linter
- MetaInfo guidelines: https://docs.flathub.org/docs/for-app-authors/metainfo-guidelines
- AppStream spec (metainfo): https://www.freedesktop.org/software/appstream/docs/
- flatpak-external-data-checker: https://github.com/flathub-infra/flatpak-external-data-checker
