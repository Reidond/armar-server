from __future__ import annotations

from pathlib import Path

import pytest

from armar_server.config.loader import (
    load_app_config,
    load_lock,
    save_app_config,
    save_lock,
)
from armar_server.config.models import AppConfig, LockEntry, LockFile
from armar_server.errors import ConfigError


def test_app_config_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "server.toml"
    cfg = AppConfig(
        name="X",
        scenario_id="{G}Missions/c.conf",
        mods=["https://reforger.armaplatform.com/workshop/AAA"],
        max_players=10,
    )
    save_app_config(path, cfg)
    loaded = load_app_config(path)
    assert loaded.name == "X"
    assert loaded.max_players == 10
    assert loaded.mods == ["https://reforger.armaplatform.com/workshop/AAA"]


def test_load_app_config_missing(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_app_config(tmp_path / "nope.toml")


def test_lock_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "armar.lock"
    lock = LockFile(
        game_version="1.7",
        mods=[LockEntry(mod_id="A", name="A", version="1.0", direct=True)],
    )
    save_lock(path, lock)
    loaded = load_lock(path)
    assert loaded.game_version == "1.7"
    assert loaded.mods[0].mod_id == "A"
    assert loaded.mods[0].direct is True
