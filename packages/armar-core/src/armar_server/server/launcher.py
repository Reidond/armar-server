"""Build container :class:`RunSpec`s for the three runtime operations.

Pure functions (no side effects) so the exact mounts/ports/command can be
asserted in tests. The CLI turns these specs into real container invocations.
"""

from __future__ import annotations

from ..config.models import AppConfig
from ..config.settings import AppSettings
from .runtime import PortMapping, RunSpec, VolumeMount
from .steamcmd import steamcmd_command


def _abs(path_str: str) -> str:
    from pathlib import Path

    return str(Path(path_str).resolve())


def _server_volumes(settings: AppSettings, *, config_ro: bool = True) -> list[VolumeMount]:
    return [
        VolumeMount(_abs(str(settings.server_dir)), "/server"),
        VolumeMount(_abs(str(settings.profile_dir)), "/profile"),
        VolumeMount(_abs(str(settings.config_dir)), "/config", read_only=config_ro),
    ]


def _ports(app: AppConfig) -> list[PortMapping]:
    ports = [
        PortMapping(app.bind_port, app.bind_port, "udp"),
        PortMapping(app.a2s_port, app.a2s_port, "udp"),
    ]
    if app.rcon_enabled:
        ports.append(PortMapping(app.rcon_port, app.rcon_port, "udp"))
    return ports


def _network(settings: AppSettings) -> str | None:
    return "host" if settings.network_mode == "host" else None


def build_steamcmd_spec(settings: AppSettings, *, validate: bool = True) -> RunSpec:
    return RunSpec(
        image=settings.image,
        command=steamcmd_command(settings.steam_app_id, install_dir="/server", validate=validate),
        volumes=[VolumeMount(_abs(str(settings.server_dir)), "/server")],
        remove=True,
        tty=True,
        workdir="/server",
    )


def build_server_command(settings: AppSettings, app: AppConfig) -> list[str]:
    return [
        f"/server/{settings.server_executable}",
        "-config",
        f"/config/{settings.rendered_config_name}",
        "-profile",
        "/profile",
        "-maxFPS",
        str(app.max_fps),
        # Trailing slash matters: the engine concatenates "addons/" onto this
        # value, so "/addons-tmp" would become "/addons-tmpaddons/".
        "-addonTempDir",
        "/addons-tmp/",
        "-backendlog",
        "-nothrow",
    ]


def build_server_spec(settings: AppSettings, app: AppConfig, *, detach: bool = False) -> RunSpec:
    network = _network(settings)
    return RunSpec(
        image=settings.image,
        command=build_server_command(settings, app),
        name=settings.container_name,
        volumes=_server_volumes(settings),
        ports=[] if network == "host" else _ports(app),
        network=network,
        detach=detach,
        interactive=not detach,
        tty=not detach,
        remove=True,
        workdir="/server",
    )


def build_list_scenarios_spec(settings: AppSettings) -> RunSpec:
    # No -config: per the wiki, scenarios are only listed when no scenario loads.
    return RunSpec(
        image=settings.image,
        command=[f"/server/{settings.server_executable}", "-listScenarios", "-nothrow"],
        volumes=_server_volumes(settings),
        network=_network(settings),
        remove=True,
        workdir="/server",
    )
