#!/usr/bin/env bash
# Thin entrypoint: make the Steam client SDK lib discoverable for the server,
# then exec whatever command was passed (steamcmd, ArmaReforgerServer, bash, ...).
set -euo pipefail

mkdir -p "${HOME}/.steam/sdk64"
if [ -f /opt/steamcmd/linux64/steamclient.so ]; then
  ln -sf /opt/steamcmd/linux64/steamclient.so "${HOME}/.steam/sdk64/steamclient.so"
fi

exec "$@"
