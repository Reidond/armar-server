"""SSH local-forward tunnel using asyncssh.

The desktop opens `ssh -L 127.0.0.1:0 <host> ...` and then talks HTTP+SSE
to the local bound port. The agent on the remote end runs on loopback TCP
+ a mandatory token.

This module is pure asyncio (no Qt) so it can be tested in isolation.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncssh

from armar_server.contracts import PROTOCOL_VERSION

# Default port the agentd listens on (loopback TCP on the remote side).
DEFAULT_AGENTD_PORT = 8477


class TunnelError(RuntimeError):
    """Raised when the SSH tunnel cannot be established."""


@dataclass(frozen=True)
class TunnelSpec:
    """A live SSH local-forward."""

    local_port: int
    ssh_user: str
    ssh_host: str
    agentd_port: int
    remote_pid: int | None  # type: ignore[type-var]


class AsyncSshTunnel:
    """SSH local-forward `127.0.0.1:0 -> <host>:agentd_port` over asyncssh.

    Connect with `await tunnel.open()`. The returned ``TunnelSpec`` gives
    the local port the HTTP client should connect to. Close with
    `await tunnel.close()`.
    """

    def __init__(
        self,
        *,
        ssh_user: str,
        ssh_host: str,
        agentd_port: int = DEFAULT_AGENTD_PORT,
        ssh_port: int = 22,
        identity_file: Path | None = None,
        known_hosts: Path | None = None,
    ) -> None:
        self._ssh_user = ssh_user
        self._ssh_host = ssh_host
        self._ssh_port = ssh_port
        self._agentd_port = agentd_port
        self._identity_file = identity_file
        self._known_hosts = known_hosts
        self._conn: asyncssh.SSHClientConnection | None = None
        self._listener: asyncssh.SSHListener | None = None

    @property
    def ssh_target(self) -> str:
        return f"{self._ssh_user}@{self._ssh_host}:{self._ssh_port}"

    async def open(self) -> TunnelSpec:
        opts: dict[str, Any] = {
            "config": [str(Path.home() / ".ssh" / "config")],
            "agent_path": os.environ.get("SSH_AUTH_SOCK"),
        }
        if self._identity_file is not None:
            opts["client_keys"] = [str(self._identity_file)]
        if self._known_hosts is not None:
            opts["known_hosts"] = str(self._known_hosts)
        else:
            # Default: use ~/.ssh/known_hosts (read-only).
            default_known = Path.home() / ".ssh" / "known_hosts"
            if default_known.exists():
                opts["known_hosts"] = str(default_known)
        try:
            self._conn = await asyncssh.connect(
                self._ssh_host,
                port=self._ssh_port,
                username=self._ssh_user,
                **opts,
            )
        except (OSError, asyncssh.PermissionDenied, asyncssh.KeyExchangeFailed) as exc:
            raise TunnelError(f"SSH connect to {self.ssh_target} failed: {exc}") from exc

        async def _on_connect(_origin_addr: Any) -> asyncssh.SSHClientSession:
            # Just return an empty session; the agentd listens on the
            # remote loopback, so we don't need a real session.
            return await _origin_addr.forward_to_tunnel(agentd_port=self._agentd_port)

        try:
            # Pick a free local port.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                free_port = s.getsockname()[1]
            # asyncssh's port forwarder API.
            self._listener = await self._conn.create_local_port_forwarder(  # type: ignore[attr-defined]
                "127.0.0.1",
                free_port,
                _on_connect,
            )
        except (OSError, asyncssh.ChannelOpenError) as exc:
            conn = self._conn
            self._conn = None
            if conn is not None:
                with contextlib.suppress(Exception):
                    await conn.close()  # type: ignore[union-attr]
            raise TunnelError(f"local-forward setup failed: {exc}") from exc

        return TunnelSpec(
            local_port=free_port,
            ssh_user=self._ssh_user,
            ssh_host=self._ssh_host,
            agentd_port=self._agentd_port,
            remote_pid=None,
        )

    async def exec(self, command: str, *, timeout: float = 30.0) -> tuple[int, str, str]:
        """Run a command on the remote host; return (exit_code, stdout, stderr)."""
        if self._conn is None:
            raise TunnelError("tunnel is not open")
        completed = await self._conn.run(command, timeout=timeout, check=False)
        return (
            completed.exit_status or 0,
            str(completed.stdout or ""),
            str(completed.stderr or ""),
        )

    async def handshake_protocol(self) -> int:
        """Call `armar-agentd --protocol-version` over SSH; return the int."""
        if shutil.which("armar-agentd") is None and not self._conn:
            # No local binary, but tunnel is up — use the remote.
            pass
        code, out, err = await self.exec("armar-agentd --protocol-version", timeout=10.0)
        if code != 0:
            raise TunnelError(f"remote handshake failed: {err.strip()}")
        return int(out.strip())

    async def close(self) -> None:
        if self._listener is not None:
            with contextlib.suppress(Exception):
                self._listener.close()
            self._listener = None
        if self._conn is not None:
            with contextlib.suppress(Exception):
                self._conn.close()
            await self._conn.wait_closed()
            self._conn = None

    async def __aenter__(self) -> AsyncSshTunnel:
        await self.open()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()


__all__ = [
    "DEFAULT_AGENTD_PORT",
    "PROTOCOL_VERSION",
    "AsyncSshTunnel",
    "TunnelError",
    "TunnelSpec",
]


# Silence "imported but unused" for type-only references used in annotations.
_ = (tempfile, Path, socket)
