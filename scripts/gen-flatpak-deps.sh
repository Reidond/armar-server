#!/bin/sh
# Generate per-arch python3-deps.<arch>.json (the pinned dependency
# module flatpak-builder uses to install third-party wheels offline)
# for the Armar Manager Flatpak build.
#
# Usage: ./scripts/gen-flatpak-deps.sh [arch ...]
#   default archs: x86_64 aarch64
#
# Requirements (run once, on the build host):
#   uv tool install --with pyyaml "git+https://github.com/johannesjh/req2flatpak"
#   (or use `uvx --from "git+https://github.com/johannesjh/req2flatpak" req2flatpak …`)
#
# Output (one per arch):
#   flatpak/python3-deps.x86_64.json
#   flatpak/python3-deps.aarch64.json
#
# Wheels are pinned by SHA-256 inside each .json, so the build is
# fully offline and reproducible. cryptography (asyncssh's only
# Rust-built dep) ships prebuilt manylinux wheels for both archs, so
# no Rust SDK extension is required.

set -eu

ARCHS="${@:-x86_64 aarch64}"
OUT_DIR="flatpak"
mkdir -p "${OUT_DIR}"

# Runtime requirements from uv.lock (omits editable installs, dev-only
# deps, and the PySide6 stack which is provided by BaseApp).
# Dev-only filter matches the `[dependency-groups] dev` group:
# basedpyright, pytest, pytest-httpx, ruff.
uv export --no-hashes --format requirements-txt 2>/dev/null \
    | grep -v '^-e ' \
    | grep -v '^#' \
    | grep -v -i -E '^(pyside6|shiboken6|pyqt5|pyqt6|basedpyright|pytest|pytest-httpx|ruff|nodejs-wheel-binaries|colorama)' \
    | grep -E '^[A-Za-z0-9._-]+\[?==' \
    | sed 's/;.*//' \
    | tr -d ' ' > "${OUT_DIR}/.runtime-reqs.txt"

REQS=$(tr '\n' ' ' < "${OUT_DIR}/.runtime-reqs.txt")

for ARCH in $ARCHS; do
    case "$ARCH" in
        x86_64)  PLATFORM=cp313-x86_64 ;;
        aarch64) PLATFORM=cp313-aarch64 ;;
        *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
    esac
    OUT="${OUT_DIR}/python3-deps.${ARCH}.json"
    echo ">> generating ${OUT} (${PLATFORM})"
    uvx --quiet --from "git+https://github.com/johannesjh/req2flatpak" \
        req2flatpak \
        --requirements $REQS \
        --target-platforms "${PLATFORM}" \
        --outfile "${OUT}"
    # req2flatpak emits every module with the same `name`. Rename
    # per-arch so the host manifest can include both without a name
    # collision.
    python3 -c "
import json, pathlib
p = pathlib.Path('${OUT}')
data = json.loads(p.read_text())
data['name'] = f'python3-deps-${ARCH}'
p.write_text(json.dumps(data, indent=4) + '\n')
"
done

rm -f "${OUT_DIR}/.runtime-reqs.txt"
echo "done. next: open flatpak/io.github.Reidond.ArmarManager.yaml"
echo "      and list the per-arch JSONs in the 'modules:' section"
echo "      (one module per arch; flatpak-builder picks the right one)."
