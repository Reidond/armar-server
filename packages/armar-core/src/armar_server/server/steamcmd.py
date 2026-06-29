"""Build the SteamCMD invocation used to install/update the server (app 1874900).

Runs *inside* the container (where SteamCMD and its 32-bit libs live). Install
and update are the same command; ``validate`` repairs file integrity.
"""

from __future__ import annotations

STEAMCMD_PATH = "/opt/steamcmd/steamcmd.sh"
DEFAULT_INSTALL_DIR = "/server"


def steamcmd_command(
    app_id: int,
    *,
    install_dir: str = DEFAULT_INSTALL_DIR,
    validate: bool = True,
) -> list[str]:
    # NB: +force_install_dir must come before +login or SteamCMD may ignore it.
    command = [
        STEAMCMD_PATH,
        "+force_install_dir",
        install_dir,
        "+login",
        "anonymous",
        "+app_update",
        str(app_id),
    ]
    if validate:
        command.append("validate")
    command.append("+quit")
    return command
