"""The `armar` CLI shim.

The actual command implementation lives in `armar_server.cli` (armar-core).
This package exists so the CLI ships as its own wheel and `armar-core` can
ship a lean wheel without the `[cli]` extra.
"""

from __future__ import annotations
