"""`machines.toml` (non-secret) + Secret Service (token) storage.

The non-secret registry lives under ``$XDG_DATA_HOME`` so the Flatpak
sandbox can use it without any ``--filesystem`` permission: the
per-app data dir is automatically mapped under ``~/.var/app/<id>/``.
"""

from __future__ import annotations

import contextlib
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w

MACHINES_FILE = "armar-manager/machines.toml"


def default_machines_path() -> Path:
    """Return the per-user machines.toml path, honoring ``$XDG_DATA_HOME``."""
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / MACHINES_FILE


@dataclass(frozen=True)
class Machine:
    name: str
    ssh_user: str
    ssh_host: str
    ssh_port: int = 22
    uds_path: str | None = None  # local machine: UDS path, not SSH

    def to_toml(self) -> dict[str, object]:
        d: dict[str, object] = {
            "name": self.name,
            "ssh_user": self.ssh_user,
            "ssh_host": self.ssh_host,
            "ssh_port": self.ssh_port,
        }
        if self.uds_path:
            d["uds_path"] = self.uds_path
        return d


class MachineStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_machines_path()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[Machine]:
        if not self._path.exists():
            return []
        data = tomllib.loads(self._path.read_text(encoding="utf-8"))
        out: list[Machine] = []
        for item in data.get("machines", []):
            out.append(
                Machine(
                    name=str(item["name"]),
                    ssh_user=str(item.get("ssh_user", "")),
                    ssh_host=str(item.get("ssh_host", "")),
                    ssh_port=int(item.get("ssh_port", 22)),
                    uds_path=item.get("uds_path"),
                )
            )
        return out

    def save(self, machines: list[Machine]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        body = {"machines": [m.to_toml() for m in machines]}
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(tomli_w.dumps(body), encoding="utf-8")
        with contextlib.suppress(OSError):
            tmp.chmod(0o600)
        tmp.replace(self._path)


__all__ = ["MACHINES_FILE", "Machine", "MachineStore", "default_machines_path"]


# Touch so the path isn't dead.
_ = Path
