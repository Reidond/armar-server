#!/usr/bin/env bash
# Lint armar-manager's QML with pyside6-qmllint.
#
# pyside6-qmllint already resolves PySide6's own bundled Qt modules
# (QtQuick, QtQuick.Controls, QtQuick.Layouts) via its default imports, so
# we only need to point it at the *system* org.kde.kirigami QML module.
# That module's location is distro-specific (Fedora: /usr/lib64/qt6/qml,
# Debian/Ubuntu: /usr/lib/<triplet>/qt6/qml), so we discover it here.
#
# Part of the project gate — see AGENTS.md. Settings live in .qmllint.ini.
set -euo pipefail
cd "$(dirname "$0")/.."

qml_dir="packages/armar-manager/src/armar_manager/qml"

# Build the candidate list of Qt6 QML import roots, most-specific first.
candidates=()
if [[ -n "${QML_IMPORT_PATH:-}" ]]; then
  IFS=':' read -ra from_env <<<"$QML_IMPORT_PATH"
  candidates+=("${from_env[@]}")
fi
if command -v qtpaths6 >/dev/null 2>&1; then
  candidates+=("$(qtpaths6 --query QT_INSTALL_QML 2>/dev/null || true)")
fi
candidates+=(/usr/lib64/qt6/qml /usr/lib/qt6/qml /usr/lib/*/qt6/qml)

kirigami_root=""
for root in "${candidates[@]}"; do
  [[ -n "$root" && -d "$root/org/kde/kirigami" ]] || continue
  kirigami_root="$root"
  break
done

import_args=()
if [[ -n "$kirigami_root" ]]; then
  import_args+=(-I "$kirigami_root")
else
  echo "error: org.kde.kirigami QML module not found." >&2
  echo "       Install it — Fedora: 'sudo dnf install kf6-kirigami';" >&2
  echo "       Debian/Ubuntu: 'sudo apt install qml6-module-org-kde-kirigami'." >&2
  echo "       Or set QML_IMPORT_PATH to a dir containing org/kde/kirigami." >&2
  exit 1
fi

exec uv run pyside6-qmllint --max-warnings 0 "${import_args[@]}" "$qml_dir"/*.qml
