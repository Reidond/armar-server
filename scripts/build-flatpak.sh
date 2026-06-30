#!/bin/sh
# Build a single-file Flatpak bundle from the current checkout.
#
# Usage (from repo root, after installing the KDE 6.10 runtimes):
#   ./scripts/build-flatpak.sh
#
# Output: dist/io.github.Reidond.ArmarManager.flatpak
#
# The manifest uses a `dir` source (repo root) so CI/tag builds always
# package the checked-out tree — no pinned git commit to bump.
#
# Prerequisites (local or CI):
#   flatpak flatpak-builder
#   flathub remote + org.kde.{Platform,Sdk}//6.10 + io.qt.PySide.BaseApp//6.10
#
# Install runtimes once:
#   flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
#   flatpak install flathub org.kde.Platform//6.10 org.kde.Sdk//6.10 io.qt.PySide.BaseApp//6.10

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_ID="io.github.Reidond.ArmarManager"
MANIFEST="$ROOT/flatpak/${APP_ID}.yaml"
OUT_DIR="${FLATPAK_OUT_DIR:-$ROOT/dist}"
BUILD_DIR="${FLATPAK_BUILD_DIR:-$ROOT/.flatpak-build/builddir}"
REPO_DIR="${FLATPAK_REPO_DIR:-$ROOT/.flatpak-build/repo}"

log() {
    printf 'build-flatpak: %s\n' "$*"
}

die() {
    log "ERROR: $*" >&2
    exit 1
}

command -v flatpak-builder >/dev/null 2>&1 || die "flatpak-builder not on PATH"
command -v flatpak >/dev/null 2>&1 || die "flatpak not on PATH"
[ -f "$MANIFEST" ] || die "manifest not found: $MANIFEST"

mkdir -p "$OUT_DIR"

log "building armar-core + armar-manager wheels for offline flatpak install"
for pkg in armar-core armar-manager; do
    uv build --package "$pkg" -o "$OUT_DIR"
done

for ref in \
    "org.kde.Sdk//6.10" \
    "org.kde.Platform//6.10" \
    "io.qt.PySide.BaseApp//6.10"
do
    if ! flatpak info "$ref" >/dev/null 2>&1 && ! flatpak --user info "$ref" >/dev/null 2>&1; then
        die "missing runtime $ref — install from flathub first (see script header)"
    fi
done

log "building $APP_ID from $MANIFEST"
flatpak-builder \
    --force-clean \
    --user \
    --install-deps-from=flathub \
    --build-only \
    "$BUILD_DIR" \
    "$MANIFEST"

# Finish + export without flatpak-builder's appstreamcli compose step (CI
# fails compose for our SVG-only icon asset; GitHub Release bundles are
# fine without regenerated AppStream catalog metadata).
flatpak build-finish \
    --share=ipc \
    --share=network \
    --socket=wayland \
    --socket=fallback-x11 \
    --device=dri \
    --socket=ssh-auth \
    --talk-name=org.freedesktop.secrets \
    --command=armar-manager \
    "$BUILD_DIR"

mkdir -p "$REPO_DIR"

flatpak build-export "$REPO_DIR" "$BUILD_DIR"

BUNDLE="$OUT_DIR/${APP_ID}.flatpak"
flatpak build-bundle "$REPO_DIR" "$BUNDLE" "$APP_ID"
log "wrote $BUNDLE"
