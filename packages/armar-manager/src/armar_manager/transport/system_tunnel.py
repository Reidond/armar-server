"""SystemSshTunnel: escape hatch that shells out to the user's ssh(1).

Used when asyncssh can't handle the auth method (FIDO/security keys,
ProxyCommand, hostnames in ~/.ssh/config that need shell expansion).
The desktop has ``--filesystem=~/.ssh/config:ro`` in the Flatpak
manifest, so users can configure whatever they need; this escape
hatch just exec's the system ``ssh`` binary to do the local-forward.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import signal
import socket
import subprocess
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from armar_server.contracts import PROTOCOL_VERSION

DEFAULT_AGENTD_PORT = 8477


class TunnelError(RuntimeError):
    pass


@dataclass
class TunnelSpec:
    local_port: int
    ssh_user: str
    ssh_host: str
    agentd_port: int
    pid: int


class SystemSshTunnel:
    """Use the system ``ssh`` binary for the local-forward."""

    def __init__(
        self,
        *,
        ssh_user: str,
        ssh_host: str,
        agentd_port: int = DEFAULT_AGENTD_PORT,
        ssh_port: int = 22,
        identity_file: Path | None = None,
        extra_options: list[str] | None = None,
    ) -> None:
        if shutil.which("ssh") is None:
            raise TunnelError("ssh binary not found on PATH")
        self._ssh_user = ssh_user
        self._ssh_host = ssh_host
        self._ssh_port = ssh_port
        self._agentd_port = agentd_port
        self._identity_file = identity_file
        self._extra_options = extra_options or []
        self._proc: subprocess.Popen[bytes] | None = None
        self._local_port: int | None = None

    @property
    def ssh_target(self) -> str:
        return f"{self._ssh_user}@{self._ssh_host}:{self._ssh_port}"

    async def open(self) -> TunnelSpec:
        # Pick a free local port first.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]

        argv: list[str] = [
            "ssh",
            "-N",  # no remote command
            "-L",
            f"127.0.0.1:{free_port}:127.0.0.1:{self._agentd_port}",
            "-p",
            str(self._ssh_port),
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
        ]
        if self._identity_file is not None:
            argv += ["-i", str(self._identity_file)]
        argv += self._extra_options
        argv.append(self.ssh_target)

        # Spawn the process; do not wait for it to exit (it serves the tunnel).
        try:
            self._proc = subprocess.Popen(argv)  # noqa: S603 — fixed argv
        except OSError as exc:
            raise TunnelError(f"ssh spawn failed: {exc}") from exc
        self._local_port = free_port

        # Best-effort wait for the local port to become connectable.
        for _ in range(20):
            with (
                contextlib.suppress(OSError),
                socket.create_connection(("127.0.0.1", free_port), timeout=0.2),
            ):
                return TunnelSpec(
                    local_port=free_port,
                    ssh_user=self._ssh_user,
                    ssh_host=self._ssh_host,
                    agentd_port=self._agentd_port,
                    pid=self._proc.pid,
                )
            await asyncio.sleep(0.1)
        # Failed to come up.
        with contextlib.suppress(ProcessLookupError):
            self._proc.terminate()
        raise TunnelError(f"ssh -L did not become connectable on 127.0.0.1:{free_port}")

    async def close(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                self._proc.send_signal(signal.SIGTERM)
            with contextlib.suppress(Exception):
                self._proc.wait(timeout=5)
        self._proc = None
        self._local_port = None

    async def __aenter__(self) -> SystemSshTunnel:
        await self.open()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()


__all__ = [
    "DEFAULT_AGENTD_PORT",
    "PROTOCOL_VERSION",
    "SystemSshTunnel",
    "TunnelError",
    "TunnelSpec",
]


_ = (AsyncIterator, Any, os)
