from __future__ import annotations

from pathlib import Path

from armar_server.config.models import AppConfig
from armar_server.config.settings import AppSettings
from armar_server.server.launcher import build_server_spec, build_steamcmd_spec


def test_steamcmd_spec_order_and_appid() -> None:
    spec = build_steamcmd_spec(AppSettings())
    cmd = spec.command
    assert cmd[0] == "/opt/steamcmd/steamcmd.sh"
    # +force_install_dir must precede +login
    assert cmd.index("+force_install_dir") < cmd.index("+login")
    assert "1874900" in cmd
    assert "validate" in cmd
    assert cmd[-1] == "+quit"


def test_server_spec_host_network(tmp_path: Path) -> None:
    settings = AppSettings(data_dir=tmp_path, network_mode="host")
    app = AppConfig(scenario_id="{X}Missions/c.conf", max_fps=72)
    spec = build_server_spec(settings, app)
    assert spec.network == "host"
    assert spec.ports == []
    assert spec.command[0].endswith("ArmaReforgerServer")
    assert "/config/server-config.json" in spec.command
    assert "72" in spec.command


def test_server_spec_bridge_ports(tmp_path: Path) -> None:
    settings = AppSettings(data_dir=tmp_path, network_mode="bridge")
    app = AppConfig(scenario_id="x", rcon_enabled=True)
    spec = build_server_spec(settings, app)
    assert spec.network is None
    mapped = {(p.host, p.container) for p in spec.ports}
    assert {(2001, 2001), (17777, 17777), (19999, 19999)} <= mapped
