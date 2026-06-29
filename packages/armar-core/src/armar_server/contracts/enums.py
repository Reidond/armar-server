"""State enums shared between `armar-agentd` and `armar-manager`.

Plain `IntEnum`s so QML can read them as ints and the wire serialises them
as ints without enum-specific code.
"""

from __future__ import annotations

from enum import IntEnum


class InstanceState(IntEnum):
    """Aggregate state of a server instance on a managed machine."""

    UNKNOWN = 0
    CREATED = 1
    STOPPED = 2
    STARTING = 3
    RUNNING = 4
    STOPPING = 5
    CRASHED = 6


class JobState(IntEnum):
    """State of a long-running operation (install / update / resolve / etc)."""

    QUEUED = 0
    RUNNING = 1
    SUCCEEDED = 2
    FAILED = 3
    CANCELLED = 4


class ConnectionState(IntEnum):
    """State of an `armar-manager` connection to a managed machine."""

    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    DEGRADED = 3
    RECONNECTING = 4
    FAILED = 5


class SseEventType(IntEnum):
    """Type of a Server-Sent Event emitted by `armar-agentd`."""

    STATE = 0
    LOG = 1
    PROGRESS = 2
    RESULT = 3
    ERROR = 4
    END = 5


__all__ = [
    "ConnectionState",
    "InstanceState",
    "JobState",
    "SseEventType",
]
