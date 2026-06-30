#!/bin/sh
# `curl | sh` installer for armar-agentd. Idempotent.
#
# Usage:
#   curl -LsSf https://github.com/<owner>/armar-server/releases/latest/download/install.sh | sh
#
# Environment variables:
#   ARMAR_VERSION   pin a specific armar-agentd version (default: latest GitHub release)
#   ARMAR_HOME      install prefix (default: ~/.local)
#   ARMAR_BIN       target binary directory (default: $ARMAR_HOME/bin)
#   UV_VERSION      pin the uv version to bootstrap when uv is missing (default: latest)

set -eu

VERSION="${ARMAR_VERSION:-}"
HOME_PREFIX="${ARMAR_HOME:-$HOME/.local}"
BIN_DIR="${ARMAR_BIN:-$HOME_PREFIX/bin}"
GITHUB_REPO="${ARMAR_GITHUB_REPO:-Reidond/armar-server}"
UV_PIN="${UV_VERSION:-}"

log() {
    printf 'armar-install: %s\n' "$*"
}

die() {
    log "ERROR: $*" >&2
    exit 1
}

have() {
    command -v "$1" >/dev/null 2>&1
}

require() {
    have "$1" || die "required command '$1' not found on PATH"
}

require curl

# --- ensure uv -------------------------------------------------------------
# The design calls for a bootstrapped, version-pinned uv. The official
# installer downloads a checksum-verified uv release; pinning UV_VERSION pins
# which release. We install into $BIN_DIR and add it to PATH for this run.
ensure_uv() {
    if have uv; then
        return 0
    fi
    log "uv not found; bootstrapping via the official installer"
    if [ -n "$UV_PIN" ]; then
        uv_url="https://astral.sh/uv/${UV_PIN}/install.sh"
    else
        uv_url="https://astral.sh/uv/install.sh"
    fi
    # UV_INSTALL_DIR / XDG_BIN_HOME tell the installer where to drop the binary.
    if ! curl -LsSf "$uv_url" | env UV_INSTALL_DIR="$BIN_DIR" XDG_BIN_HOME="$BIN_DIR" sh; then
        die "uv bootstrap failed (see $uv_url)"
    fi
    PATH="$BIN_DIR:$PATH"
    export PATH
    have uv || die "uv still not on PATH after bootstrap (looked in $BIN_DIR)"
}

ensure_uv

# --- ensure a container runtime -------------------------------------------
# The agent drives rootless podman (preferred) or docker. Neither is installed
# by this script (it needs distro packages + a user session), but we fail with
# an actionable message rather than letting `armar-agentd` blow up later.
ensure_runtime() {
    if have podman || have docker; then
        return 0
    fi
    die "no container runtime found: install 'podman' (recommended, rootless) or 'docker' and re-run"
}

ensure_runtime

# Pick the latest release tag if VERSION is not pinned.
if [ -z "$VERSION" ]; then
    log "resolving latest release from $GITHUB_REPO"
    VERSION=$(curl -sSf "https://api.github.com/repos/$GITHUB_REPO/releases/latest" \
        | sed -n 's/^.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1)
    [ -n "$VERSION" ] || die "could not resolve latest release tag"
fi
# Tags are like vX.Y.Z; the PyPI version is the part after the leading 'v'.
PKG_VERSION="${VERSION#v}"
log "installing armar-agentd $PKG_VERSION"

# Detect platform (informational; uv resolves the right wheels).
case "$(uname -sm)" in
    Linux\ x86_64)  PLATFORM=x86_64 ;;
    Linux\ aarch64) PLATFORM=aarch64 ;;
    *)              die "unsupported platform: $(uname -sm) (Linux x86_64/aarch64 only)" ;;
esac
log "platform: linux/$PLATFORM"

# Install the agent as an isolated, easily-upgraded uv tool from the GitHub
# Release wheels (no PyPI). `install.sh` is attached to every tag release.
RELEASE_URL="https://github.com/${GITHUB_REPO}/releases/download/${VERSION}"
log "installing from GitHub release ${RELEASE_URL}"
uv tool install "armar-agentd==${PKG_VERSION}" --with armar-core \
    --find-links "${RELEASE_URL}" || die "uv tool install failed (are release wheels published?)"

# Persist the tool bin directory hint for the user.
case :$PATH: in
    *":$BIN_DIR:"*) ;;
    *) log "note: add $BIN_DIR to your PATH to use the 'armar-agentd' command" ;;
esac

log "running armar-agentd install (systemd --user, linger)"
PATH="$BIN_DIR:$PATH" armar-agentd install

log "done. To add this machine to the manager, the desktop reads the token via:"
log "    PATH=$BIN_DIR:\$PATH armar-agentd token print"
