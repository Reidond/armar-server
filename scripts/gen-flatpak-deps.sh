#!/bin/sh
# Generate python3-deps for Flatpak: third-party wheels vendored from uv export.
#
# Usage: ./scripts/gen-flatpak-deps.sh [output-dir]
#   default output-dir: flatpak/python3-deps
set -eu

OUT_DIR="${1:-flatpak/python3-deps}"
mkdir -p "$OUT_DIR"

# Filter out pyside6 + shiboken6 — they come from the io.qt.PySide.BaseApp base.
uv export --no-hashes --format requirements-txt \
    | grep -v -i -E '^(pyside6|shiboken6)==' \
    | uv pip download --dest "$OUT_DIR" --no-deps -

# req2flatpak would do sha256 pinning + per-arch rebuild; we leave that
# to the build host. The output is a directory of wheels ready for the
# flatpak-builder stage.
echo "wrote $(ls "$OUT_DIR" | wc -l) wheels to $OUT_DIR"
