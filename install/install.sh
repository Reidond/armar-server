#!/bin/sh
# `curl | sh` installer for armar-agentd. Idempotent.
#
# Usage:
#   curl -LsSf https://github.com/<owner>/armar-server/releases/latest/download/install.sh | sh
#
# Environment variables:
#   ARMAR_VERSION   pin a specific version (default: latest GitHub release)
#   ARMAR_HOME      install prefix (default: ~/.local)
#   ARMAR_BIN       target binary directory (default: $ARMAR_HOME/bin)

set -eu

VERSION="${ARMAR_VERSION:-}"
HOME_PREFIX="${ARMAR_HOME:-$HOME/.local}"
BIN_DIR="${ARMAR_BIN:-$HOME_PREFIX/bin}"
GITHUB_REPO="${ARMAR_GITHUB_REPO:-anomalyco/armar-server}"

log() {
    printf 'armar-install: %s\n' "$*"
}

die() {
    log "ERROR: $*" >&2
    exit 1
}

require() {
    command -v "$1" >/dev/null 2>&1 || die "required command '$1' not found on PATH"
}

require curl
require shasum || require sha256sum

# Pick the latest release tag if VERSION is not pinned.
if [ -z "$VERSION" ]; then
    log "resolving latest release from $GITHUB_REPO"
    VERSION=$(curl -sSf "https://api.github.com/repos/$GITHUB_REPO/releases/latest" \
        | sed -n 's/^.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1)
    [ -n "$VERSION" ] || die "could not resolve latest release tag"
fi
log "installing armar-agentd $VERSION"

# Detect platform.
case "$(uname -sm)" in
    Linux\ x86_64)  PLATFORM=manylinux2014_x86_64 ;;
    Linux\ aarch64) PLATFORM=manylinux2014_aarch64 ;;
    *)              die "unsupported platform: $(uname -sm)" ;;
esac

# Use uv to install the agentd CLI as a uv tool (lean, isolated, easy to upgrade).
require uv
log "installing via uv tool ($PLATFORM)"
uv tool install "armar-agentd==$VERSION" --with armar-core || die "uv tool install failed"

# Persist the tool bin directory hint for the user.
case :$PATH: in
    *":$BIN_DIR:"*) ;;
    *) log "note: add $BIN_DIR to your PATH to use the 'armar-agentd' command" ;;
esac

log "running armar-agentd install (systemd --user, linger)"
PATH="$BIN_DIR:$PATH" armar-agentd install

log "done. To add another machine to the manager, run:"
log "    PATH=$BIN_DIR:\$PATH armar-agentd token print"
