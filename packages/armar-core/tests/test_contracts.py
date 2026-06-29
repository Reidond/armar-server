"""Round-trip tests for the shared contracts DTOs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import SecretStr, ValidationError

from armar_server.contracts import (
    PROTOCOL_VERSION,
    AgentInfo,
    AppConfigUpdate,
    AppConfigView,
    ConnectionState,
    InstanceCreate,
    InstanceDetail,
    InstanceState,
    InstanceSummary,
    JobRef,
    JobState,
    JobView,
    LifecycleEvent,
    LogEvent,
    ProgressEvent,
    SseEventType,
    StatusView,
)


def test_protocol_version_is_a_single_int() -> None:
    assert isinstance(PROTOCOL_VERSION, int)
    assert PROTOCOL_VERSION >= 1


def test_agent_info_does_not_expose_token() -> None:
    info = AgentInfo(
        agent_version="0.1.0",
        protocol_version=PROTOCOL_VERSION,
        hostname="host-a",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    dumped = info.model_dump()
    assert "token" not in dumped
    assert dumped["protocol_version"] == PROTOCOL_VERSION


def test_instance_summary_roundtrip() -> None:
    s = InstanceSummary(
        slug="alpha",
        name="Alpha",
        state=InstanceState.RUNNING,
        game_port=2001,
        a2s_port=17777,
        rcon_port=19999,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    again = InstanceSummary.model_validate(s.model_dump())
    assert again == s


def test_instance_detail_extends_summary() -> None:
    d = InstanceDetail(
        slug="alpha",
        name="Alpha",
        game_port=2001,
        a2s_port=17777,
        rcon_port=19999,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        container_name="armar-alpha",
        server_dir="/srv/alpha",
        profile_dir="/srv/alpha/profile",
        config_dir="/srv/alpha/config",
    )
    assert d.container_name == "armar-alpha"


def test_instance_create_validates_slug() -> None:
    InstanceCreate(name="X", slug="ok")
    with pytest.raises(ValidationError):
        InstanceCreate(name="X", slug="")  # min_length=1


def test_job_ref_serialises_just_job_id() -> None:
    ref = JobRef(job_id="abc")
    assert ref.model_dump() == {"job_id": "abc"}


def test_job_view_states_are_ints() -> None:
    view = JobView(
        job_id="abc",
        state=JobState.SUCCEEDED,
        kind="install",
    )
    assert isinstance(view.model_dump()["state"], int)
    assert view.model_dump()["state"] == int(JobState.SUCCEEDED)


def test_status_view_optional_fields_default_none() -> None:
    base = InstanceSummary(
        slug="alpha",
        name="Alpha",
        game_port=2001,
        a2s_port=17777,
        rcon_port=19999,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    view = StatusView(instance=base, container_running=True)
    assert view.players_online is None
    assert view.last_log_line is None


def test_log_event_seq_required() -> None:
    LogEvent(seq=1, ts=datetime(2026, 1, 1, tzinfo=UTC), line="hello")
    with pytest.raises(ValidationError):
        LogEvent(ts=datetime(2026, 1, 1, tzinfo=UTC), line="hello")  # type: ignore[call-arg]


def test_progress_event_pct_bounds() -> None:
    ProgressEvent(seq=1, pct=0.0)
    ProgressEvent(seq=2, pct=100.0)
    with pytest.raises(ValidationError):
        ProgressEvent(seq=3, pct=-0.1)
    with pytest.raises(ValidationError):
        ProgressEvent(seq=4, pct=100.1)


def test_lifecycle_event_carries_log_and_progress() -> None:
    evt = LifecycleEvent(
        seq=1,
        type=SseEventType.LOG,
        log=LogEvent(seq=1, ts=datetime(2026, 1, 1, tzinfo=UTC), line="x"),
    )
    assert evt.type == SseEventType.LOG
    assert evt.log is not None and evt.log.line == "x"


def test_app_config_view_secrets_are_masks() -> None:
    view = AppConfigView.model_validate(
        {
            "raw": {"rcon": {"enabled": True}},
            "secrets": {"rcon_password": {"set": True}},
        }
    )
    dumped = view.model_dump()
    assert dumped["secrets"]["rcon_password"] == {"set": True}
    assert "value" not in dumped["secrets"]["rcon_password"]


def test_app_config_update_uses_secret_str() -> None:
    update = AppConfigUpdate(
        raw={"server": {"name": "new"}},
        secrets={"rcon_password": SecretStr("topsecret")},
    )
    dumped = update.model_dump()
    # SecretStr is serialised as '**********' (or the configured format).
    assert dumped["secrets"]["rcon_password"] != "topsecret"  # noqa: S105 — test fixture


def test_int_enums_have_distinct_int_values() -> None:
    states = {s.value for s in InstanceState}
    assert len(states) == len(list(InstanceState))
    assert {s.value for s in JobState} == set(range(len(JobState)))
    assert {s.value for s in SseEventType} == set(range(len(SseEventType)))


def test_connection_state_int_values() -> None:
    assert ConnectionState.DISCONNECTED == 0
    assert ConnectionState.CONNECTED == 2
    assert ConnectionState.FAILED == 5
