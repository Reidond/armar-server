# Spec: multi-server-desktop-p4 — distribution & ops hardening

> Sub-spec expanded from the parent epic `.specs/multi-server-desktop/` (Phase **P4**,
> "polish + distribution"). The Flatpak manifest, `scripts/release.py`, `cd.yml`, and the
> `SystemSshTunnel` escape hatch already shipped. This sub-spec closes the **offline-testable**
> P4 gaps and records the rest (which need external infra) as explicit follow-ups.

## Goals (this session — testable in the offline gate)

- **`install/install.sh` bootstrap**: per the design, "bootstrap uv (pinned, sha256-verified) +
  ensure podman". Today the script hard-`require`s `uv` and never ensures a container runtime, and
  its `require shasum || require sha256sum` line is dead (the first `require` `exit`s on a
  sha256sum-only host before the `||`). Make it:
  - install `uv` via the official installer (honoring a pinned `UV_VERSION`) when missing, instead
    of failing;
  - ensure a container runtime (`podman` or `docker`) is present, with a clear, actionable error
    when neither is;
  - drop the dead sha-tool check;
  - stay idempotent and `shellcheck`-clean.

## Done after the initial slice

- **Flatpak `keyring` vendoring**: `flatpak/python3-deps.*.json` regenerated via
  `scripts/gen-flatpak-deps.sh` to include the keyring closure (`keyring`, `secretstorage`,
  `jeepney`, `jaraco.classes/context/functools`, `more-itertools`). The generator now (a) drops
  non-Linux marker rows so keyring's win32-only `pywin32-ctypes` is not vendored, and (b) stamps
  each per-arch module with a module-level `only-arches` so flatpak-builder runs only the module
  matching the build target (otherwise the wrong-arch module's `pip install --no-index` fails on
  the arch-specific binary wheels). Verifying with a real Flatpak build still needs
  `org.flatpak.Builder` + the KDE runtime (out of the offline gate).

## Non-goals / follow-ups (need external infra — tracked, not done here)

- A **real Flatpak build** (`org.flatpak.Builder` + `flatpak-builder-lint`) to verify the
  regenerated manifest end to end.
- **Flathub submission** + adding the `.flatpak` bundle to the rolling `preview` prerelease
  (`cd.yml`) — needs a Flatpak build runner; deferred.
- **Token-rotation UX in QML** — the transport supports it (`ConnectionManager.rotateToken`);
  wiring a button needs the Kirigami runtime to lint/verify; deferred with UI polish.
- **F0** (PyPI name claim + Trusted Publishers) — external prerequisite before the first tag.

## Acceptance criteria

- [ ] `install.sh` installs `uv` via the official `astral.sh` installer when absent (pinned to
      `UV_VERSION` when set), then proceeds; it does not abort merely because `uv` is missing.
- [ ] `install.sh` succeeds when a container runtime exists and prints a clear error naming both
      `podman` and `docker` when neither does.
- [ ] No dead `require shasum || require sha256sum` line.
- [ ] `shellcheck install/install.sh` passes (added to CI alongside the existing shellcheck job).

## Tests

- `shellcheck install/install.sh` (static). No unit test harness for the network-touching install
  path; behaviour is asserted by shellcheck + manual review of the control flow.
