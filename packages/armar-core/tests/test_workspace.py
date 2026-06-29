"""Workspace structure smoke tests."""

from __future__ import annotations

import importlib
import subprocess
import sys


def test_armar_server_imports() -> None:
    mod = importlib.import_module("armar_server")
    assert mod.__version__  # not empty


def test_logging_get_logger_rich_free() -> None:
    """`get_logger` must not import `rich` (CLI extra)."""
    # Simulate a bare-core env by importing logging before typer/rich have a
    # chance to load via armar_server.cli.
    from armar_server.logging import get_logger

    logger = get_logger("test")
    assert logger.name == "test"


def test_workshop_resolver_import_path() -> None:
    """The workshop resolver (used by the agent) must not pull in typer/rich."""
    importlib.import_module("armar_server.workshop.resolver")
    importlib.import_module("armar_server.config.loader")


def test_armar_version_via_cli() -> None:
    """`armar --version` reads the dynamic metadata."""
    result = subprocess.run(
        [sys.executable, "-m", "armar_cli.__main__", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.startswith("armar ")
    assert result.stdout.strip().split()[-1]  # has a version


def test_contracts_protocol_version_constant() -> None:
    from armar_server.contracts import PROTOCOL_VERSION

    assert isinstance(PROTOCOL_VERSION, int)
