"""armar-server: run a modded Arma Reforger dedicated server with uv.

A small CLI that turns Arma Workshop URLs into a valid Reforger dedicated-server
config and runs the server in a container (Podman/Docker).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("armar-core")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
