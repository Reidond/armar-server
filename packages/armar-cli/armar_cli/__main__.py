"""`armar-core` shim: re-export the Typer app from `armar_server.cli`."""

from __future__ import annotations

from armar_server.cli import app

__all__ = ["app"]


if __name__ == "__main__":
    app()
