"""Transport: SSH tunnel, HTTP+SSE agent client, host-key TOFU."""

from .client import AgentClient
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
    "HostKey",
    "HostKeyMismatch",
    "HostKeyPinner",
    "HostKeyRejected",
    "HttpAgentClient",
    "LocalConnection",
    "SystemSshTunnel",
    "TunnelError",
    "TunnelSpec",
    "default_known_hosts_path",
]
