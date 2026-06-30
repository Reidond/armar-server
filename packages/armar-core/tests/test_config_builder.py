from __future__ import annotations

import json

from armar_server.config.loader import render_server_config
from armar_server.config.models import AppConfig, LockEntry, LockFile
from armar_server.server.config_builder import build_server_config


def test_build_and_render() -> None:
    app = AppConfig(
        name="Test",
        scenario_id="{X}Missions/c.conf",
        battleye=False,
        max_players=32,
        a2s_port=17777,
    )
    lock = LockFile(
        mods=[
            LockEntry(mod_id="AAA", name="Mod A", version="1.0", direct=True),
            LockEntry(mod_id="BBB", name="Dep B", version=None, direct=False),
        ]
    )
    sc = build_server_config(app, lock, public_address="10.0.0.5")

    assert sc.publicAddress == "10.0.0.5"
    assert sc.game.scenarioId.endswith("c.conf")
    assert sc.game.maxPlayers == 32
    assert sc.game.gameProperties.fastValidation is True  # always on by default
    assert sc.game.gameProperties.battlEye is False
    assert sc.rcon is None
    assert [m.modId for m in sc.game.mods] == ["AAA", "BBB"]

    data = json.loads(render_server_config(sc))
    assert data["game"]["mods"][0] == {"modId": "AAA", "name": "Mod A", "version": "1.0"}
    assert "version" not in data["game"]["mods"][1]  # None omitted
    assert "operating" not in data  # empty operating dropped
    assert data["a2s"]["port"] == 17777


def test_rcon_enabled() -> None:
    app = AppConfig(
        scenario_id="{X}Missions/c.conf",
        rcon_enabled=True,
        rcon_password="test-rcon-pw",
        rcon_port=19999,
    )
    sc = build_server_config(app, LockFile())
    assert sc.rcon is not None
    assert sc.rcon.password == "test-rcon-pw"

    data = json.loads(render_server_config(sc))
    assert data["rcon"]["port"] == 19999
    assert data["rcon"]["password"] == "test-rcon-pw"


def test_game_properties_passthrough() -> None:
    app = AppConfig(
        scenario_id="{X}Missions/c.conf",
        game_properties={"disableThirdPerson": True, "serverMaxViewDistance": 2500},
    )
    sc = build_server_config(app, LockFile())
    data = json.loads(render_server_config(sc))
    assert data["game"]["gameProperties"]["disableThirdPerson"] is True
    assert data["game"]["gameProperties"]["serverMaxViewDistance"] == 2500
