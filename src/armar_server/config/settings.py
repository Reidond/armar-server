"""Operational settings (paths, container runtime, ports, Arma constants).

Loaded once and passed to services. Overridable via ``ARMAR_*`` environment
variables or a local ``.env``. Services read tunables from here — never from
``os.environ`` directly and never as magic constants.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARMAR_",
        env_file=".env",
        extra="ignore",
    )

    # --- project layout (relative to the working directory) ---
    data_dir: Path = Path("data")
    config_file: Path = Path("server.toml")
    lock_file: Path = Path("armar.lock")
    rendered_config_name: str = "server-config.json"

    # --- container runtime ---
    runtime: str = "podman"  # "podman" | "docker"
    image: str = "armar-reforger:latest"
    container_name: str = "armar-reforger"
    network_mode: str = "host"  # "host" | "bridge"
    selinux_relabel: bool = True  # add :Z to volume mounts (Fedora/SELinux)
    userns_keep_id: bool = True  # rootless podman: map container user to host uid

    # --- Arma Reforger constants ---
    steam_app_id: int = 1874900
    server_executable: str = "ArmaReforgerServer"
    max_fps: int = 60

    # --- default ports (UDP) ---
    game_port: int = 2001
    a2s_port: int = 17777
    rcon_port: int = 19999

    @property
    def server_dir(self) -> Path:
        """Host dir holding the SteamCMD-installed server binary."""
        return self.data_dir / "server"

    @property
    def profile_dir(self) -> Path:
        """Host dir for logs + downloaded mod storage (the server ``-profile``)."""
        return self.data_dir / "profile"

    @property
    def config_dir(self) -> Path:
        """Host dir holding the rendered Reforger JSON config."""
        return self.data_dir / "config"

    @property
    def rendered_config_path(self) -> Path:
        return self.config_dir / self.rendered_config_name
