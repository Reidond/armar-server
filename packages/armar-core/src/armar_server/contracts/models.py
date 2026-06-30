"""Pydantic DTOs shared between `armar-agentd` and `armar-manager`.

`SecretStr` is used for fields that hold credentials the manager should
**write** but never **read back**; the view-side `AppConfigView` returns
`{set: bool}` for those fields so a logged-in operator can see whether a
value is configured but not what it is.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .enums import InstanceState, JobState, SseEventType

# -- Identity ---------------------------------------------------------------


class AgentInfo(BaseModel):
    """Identity of an `armar-agentd` instance — exposed by `GET /api/v1/info`.

    **Never** includes the auth token.
    """

    model_config = ConfigDict(extra="forbid")

    agent_version: str
    protocol_version: int
    hostname: str
    started_at: datetime


# -- Instances --------------------------------------------------------------


class InstanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    state: InstanceState = InstanceState.UNKNOWN
    game_port: int
    a2s_port: int
    rcon_port: int
    created_at: datetime


class InstanceDetail(InstanceSummary):
    container_name: str
    server_dir: str
    profile_dir: str
    config_dir: str
    network_mode: str = "host"
    schema_version: int = 1


class InstanceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    slug: str | None = Field(default=None, min_length=1, max_length=32)
    game_port: int | None = Field(default=None, ge=1, le=65535)
    a2s_port: int | None = Field(default=None, ge=1, le=65535)
    rcon_port: int | None = Field(default=None, ge=1, le=65535)


# -- Jobs / SSE -------------------------------------------------------------


class JobRef(BaseModel):
    """Returned by 202-Accepted endpoints to point at a long-running job."""

    model_config = ConfigDict(extra="forbid")

    job_id: str


class JobView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    state: JobState
    kind: str
    instance_slug: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


# -- Status / logs ----------------------------------------------------------


class StatusView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance: InstanceSummary
    container_running: bool
    cpu_pct: float | None = None
    mem_bytes: int | None = None
    players_online: int | None = None
    last_log_line: str | None = None


class LogEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int
    ts: datetime
    stream: str = "stdout"  # stdout|stderr
    line: str


class ProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int
    pct: float = Field(ge=0.0, le=100.0)
    label: str | None = None


class LifecycleEvent(BaseModel):
    """A state/progress/log event in the unified SSE stream."""

    model_config = ConfigDict(extra="forbid")

    seq: int
    type: SseEventType
    state: InstanceState | None = None
    log: LogEvent | None = None
    progress: ProgressEvent | None = None
    result: str | None = None
    error: str | None = None


# -- Config (secrets handled with SecretStr / {set:bool}) -------------------


class _SecretSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    set: bool


class AppConfigView(BaseModel):
    """Read-side view of an instance's `server.toml` payload.

    Secrets are projected as `{set: bool}` so the UI can show that a value
    is configured without leaking the value itself.
    """

    model_config = ConfigDict(extra="forbid")

    raw: dict[str, object]
    secrets: dict[str, _SecretSet] = Field(default_factory=dict)


class AppConfigUpdate(BaseModel):
    """Write-side update — omit a secret field to keep its current value.

    Setting a secret to `null` clears it; setting it to a string replaces it.
    """

    model_config = ConfigDict(extra="forbid")

    raw: dict[str, object] = Field(default_factory=dict)
    secrets: dict[str, SecretStr | None] = Field(default_factory=dict)


__all__ = [
    "AgentInfo",
    "AppConfigUpdate",
    "AppConfigView",
    "InstanceCreate",
    "InstanceDetail",
    "InstanceSummary",
    "JobRef",
    "JobView",
    "LifecycleEvent",
    "LogEvent",
    "ProgressEvent",
    "StatusView",
]
