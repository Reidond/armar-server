"""Structured logging setup built on Rich.

`get_logger` is intentionally rich-free so bare `armar-core` (the wheel the
agent depends on) can import it without dragging in the ``rich`` package.
``setup_logging`` is CLI-only and lazy-imports ``RichHandler`` inside the
function body.
"""

from __future__ import annotations

import logging

__all__ = ["get_logger", "setup_logging"]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def setup_logging(*, verbose: bool = False) -> None:
    """Configure root logging once with a Rich handler (CLI-only)."""
    from rich.logging import RichHandler  # lazy: rich is a [cli] extra

    level = logging.DEBUG if verbose else logging.INFO
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, RichHandler):
            root.setLevel(level)
            return
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False, markup=True)],
        force=True,
    )
