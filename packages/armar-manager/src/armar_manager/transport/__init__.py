"""Transport: SSH tunnel, HTTP+SSE agent client, host-key TOFU."""

from .client import AgentClient
from .connection import (
    DialResult,
    Tunnel,
    TunnelFactory,
    dial_remote,
    rotate_remote_token,
)
from .hostkeys import (
    HostKey,
    HostKeyMismatch,
    HostKeyPinner,
    HostKeyRejected,
    default_known_hosts_path,
)
from .http import HttpAgentClient, LocalConnection
from .system_tunnel import SystemSshTunnel
from .tunnel import (
    DEFAULT_AGENTD_PORT,
    AsyncSshTunnel,
    TunnelError,
    TunnelSpec,
)

__all__ = [
    "DEFAULT_AGENTD_PORT",
    "AgentClient",
    "AsyncSshTunnel",
    "DialResult",
    "HostKey",
    "HostKeyMismatch",
    "HostKeyPinner",
    "HostKeyRejected",
    "HttpAgentClient",
    "LocalConnection",
    "SystemSshTunnel",
    "Tunnel",
    "TunnelError",
    "TunnelFactory",
    "TunnelSpec",
    "default_known_hosts_path",
    "dial_remote",
    "rotate_remote_token",
]
