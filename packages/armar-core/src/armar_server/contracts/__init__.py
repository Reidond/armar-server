"""Shared wire-contract DTOs, state enums, and protocol version.

Imported by `armar-agentd` (server) and `HttpAgentClient` (client). Pure
pydantic + stdlib enums; **no fastapi, no httpx** dependency.
"""

from __future__ import annotations

from .enums import (
    ConnectionState,
    InstanceState,
    JobState,
    SseEventType,
)
from .models import (
    AgentInfo,
    AppConfigUpdate,
    AppConfigView,
    InstanceCreate,
    InstanceDetail,
    InstanceSummary,
    JobRef,
    JobView,
    LifecycleEvent,
    LogEvent,
    ProgressEvent,
    StatusView,
)

PROTOCOL_VERSION = 1

__all__ = [
    "PROTOCOL_VERSION",
    "AgentInfo",
    "AppConfigUpdate",
    "AppConfigView",
    "ConnectionState",
    "InstanceCreate",
    "InstanceDetail",
    "InstanceState",
    "InstanceSummary",
    "JobRef",
    "JobState",
    "JobView",
    "LifecycleEvent",
    "LogEvent",
    "ProgressEvent",
    "SseEventType",
    "StatusView",
]
