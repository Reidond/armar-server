"""CLI smoke tests: ``--version`` and the global ``-I/--instance`` routing.

These exercise the Typer wiring (callback + ``_settings()`` resolution)
without spawning containers or hitting the network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from armar_server import __version__
from armar_server.cli import app

runner = CliRunner()


def test_version_flag_prints_metadata_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"armar {__version__}"


def test_instance_flag_routes_init_into_the_registry_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    # Create a registry instance, then `init` under `-I <slug>` must write
    # the starter server.toml into that instance's namespaced layout.
    created = runner.invoke(app, ["instance", "create", "--slug", "alpha", "--name", "Alpha"])
    assert created.exit_code == 0, created.stdout

    initialized = runner.invoke(app, ["-I", "alpha", "init"])
    assert initialized.exit_code == 0, initialized.stdout

    instance_config = tmp_path / "data" / "instances" / "alpha" / "server.toml"
    assert instance_config.exists()
    # The legacy cwd layout must be untouched by the `-I` path.
    assert not (tmp_path / "server.toml").exists()


def test_instance_flag_unknown_slug_errors_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["-I", "ghost", "config"])
    assert result.exit_code == 1
    assert "ghost" in result.stdout
    assert "not found" in result.stdout


def test_no_instance_flag_uses_cwd_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "server.toml").exists()
