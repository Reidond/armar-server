"""Agent settings: bind address, token, paths.

The agent is the small FastAPI service that runs on each managed machine.
The transport is:

- **Remote** machines: TCP on loopback + mandatory token (an ``ssh -L``
  forward is TCP→TCP, so the remote end must listen on loopback TCP).
- **Local** machine: UDS with the token disabled.

`AgentSettings` rejects non-loopback/wildcard binds.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_TCP_PORT = 65535
MIN_TCP_PORT = 1
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "armar-agentd"


class BindError(ValueError):
    """Raised when the configured bind address is not loopback."""


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARMAR_AGENTD_",
        env_file=".env",
        extra="ignore",
    )

    # Transport
    bind_host: str = "127.0.0.1"
    bind_port: int = 8477
    # When set, bind a Unix-domain socket at this path (no token required).
    # The CLI on the local machine uses this.
    uds_path: Path | None = None
    # Disable token check (only valid with UDS).
    token_disabled: bool = False

    # Auth
    # When set, the agent requires this token on every request. The desktop
    # stores it in the Secret Service. /healthz, /readyz are exempt.
    token: str | None = None

    # Paths
    data_dir: Path = Field(default_factory=lambda: DEFAULT_DATA_DIR)
    instances_dir: Path | None = None  # defaults to data_dir/instances

    @field_validator("bind_host")
    @classmethod
    def _validate_bind_host(cls, value: str) -> str:
        if value in LOOPBACK_HOSTS or value == "0.0.0.0":
            return value
        raise BindError(
            f"bind_host must be loopback (one of {sorted(LOOPBACK_HOSTS)}) or "
            f"explicitly '0.0.0.0' for tests; got {value!r}"
        )

    def effective_instances_dir(self) -> Path:
        return self.instances_dir or (self.data_dir / "instances")

    def runtime_binary(self) -> str:
        """Default container runtime binary used for `doctor` checks."""
        return "podman"


__all__ = [
    "LOOPBACK_HOSTS",
    "MAX_TCP_PORT",
    "MIN_TCP_PORT",
    "AgentSettings",
    "BindError",
]
