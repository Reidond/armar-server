"""Qt-free remote-dial helpers: obtain/persist the agent token + connect.

This is the seam the parent P1 design left deferred: a remote
``armar-agentd`` listens on loopback TCP and requires a bearer token.
On dial we use a stored token; if none, we obtain it **once** over
SSH-exec (``armar-agentd token print``) and persist it to the Secret
Service (see ``secrets/tokens.py``). The token travels only as the
``Authorization`` header — never over HTTP, never to ``machines.toml``.

Everything here is pure asyncio (no Qt, no real sshd) so it is unit
testable with a fake tunnel + a fake client.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from armar_server.contracts import PROTOCOL_VERSION

from .client import AgentClient
from .http import HttpAgentClient
from .tunnel import AsyncSshTunnel, TunnelError, TunnelSpec

if TYPE_CHECKING:
    from ..secrets import Machine, SecretTokenStore

# Fixed argv-strings run on the remote host over SSH-exec. Named without
# "token"/"secret"/"password" so the value (which contains "token") is not
# misread as a hardcoded credential.
_AGENTD_PRINT = "armar-agentd token print"
_AGENTD_ROTATE = "armar-agentd token rotate"


class Tunnel(Protocol):
    """The subset of the SSH tunnel that :func:`dial_remote` needs."""

    async def open(self) -> TunnelSpec: ...
    async def exec(self, command: str, *, timeout: float = ...) -> tuple[int, str, str]: ...
    async def close(self) -> None: ...


TunnelFactory = Callable[..., Tunnel]
ClientFactory = Callable[..., AgentClient]


@dataclass
class DialResult:
    client: AgentClient
    tunnel: Tunnel


def _default_tunnel_factory(**kwargs: object) -> Tunnel:
    return AsyncSshTunnel(**kwargs)  # type: ignore[arg-type]


def _default_client_factory(*, base_url: str, token: str | None) -> AgentClient:
    return HttpAgentClient(base_url=base_url, token=token)


async def _obtain_token(tunnel: Tunnel, command: str) -> str:
    code, out, err = await tunnel.exec(command)
    token = out.strip()
    if code != 0 or not token:
        detail = err.strip() or "no token on stdout"
        raise TunnelError(f"`{command}` failed (exit {code}): {detail}")
    return token


async def dial_remote(
    machine: Machine,
    *,
    token_store: SecretTokenStore,
    protocol_version: int = PROTOCOL_VERSION,
    tunnel_factory: TunnelFactory = _default_tunnel_factory,
    client_factory: ClientFactory = _default_client_factory,
) -> DialResult:
    """Open the SSH local-forward, ensure a token, connect, verify protocol.

    Token resolution: a stored token is reused; otherwise it is fetched
    once via ``armar-agentd token print`` and persisted. On any failure
    the tunnel/client opened so far is closed and ``TunnelError`` is
    raised — nothing partial is left behind, and a failed token fetch
    persists nothing.
    """
    tunnel = tunnel_factory(
        ssh_user=machine.ssh_user,
        ssh_host=machine.ssh_host,
        ssh_port=machine.ssh_port,
    )
    spec = await tunnel.open()
    try:
        token = token_store.get_token(machine.name)
        if not token:
            token = await _obtain_token(tunnel, _AGENTD_PRINT)
            token_store.set_token(machine.name, token)
        client = client_factory(
            base_url=f"http://127.0.0.1:{spec.local_port}",
            token=token,
        )
    except BaseException:
        await tunnel.close()
        raise

    try:
        info = await client.info()
        if info.protocol_version != protocol_version:
            raise TunnelError(
                f"protocol version mismatch: agentd={info.protocol_version} "
                f"manager={protocol_version}"
            )
    except BaseException as exc:
        with contextlib.suppress(Exception):
            await client.close()
        await tunnel.close()
        if isinstance(exc, TunnelError):
            raise
        raise TunnelError(f"agent handshake failed: {exc}") from exc

    return DialResult(client=client, tunnel=tunnel)


async def rotate_remote_token(
    machine: Machine,
    *,
    token_store: SecretTokenStore,
    tunnel: Tunnel,
) -> str:
    """Rotate the agent token via SSH-exec and persist the new value.

    The caller must re-dial afterwards: the running agent now expects the
    new token, so the existing (old-token) client will start to 401.
    """
    token = await _obtain_token(tunnel, _AGENTD_ROTATE)
    token_store.set_token(machine.name, token)
    return token


__all__ = [
    "ClientFactory",
    "DialResult",
    "Tunnel",
    "TunnelFactory",
    "dial_remote",
    "rotate_remote_token",
]
