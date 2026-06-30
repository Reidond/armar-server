from __future__ import annotations

from pathlib import Path

import pytest

from armar_server.config.settings import AppSettings


def test_defaults_and_derived_paths() -> None:
    settings = AppSettings(data_dir=Path("data"))
    assert settings.steam_app_id == 1874900
    assert settings.runtime == "podman"
    assert settings.server_dir == Path("data/server")
    assert settings.profile_dir == Path("data/profile")
    assert settings.rendered_config_path == Path("data/config/server-config.json")
    assert settings.instances_dir == Path("data/instances")


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARMAR_RUNTIME", "docker")
    monkeypatch.setenv("ARMAR_NETWORK_MODE", "bridge")
    settings = AppSettings()
    assert settings.runtime == "docker"
    assert settings.network_mode == "bridge"
