"""Live log + status routes for `armar-agentd`."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from armar_server.config.registry import InstanceNotFoundError, InstanceRegistry
from armar_server.config.settings import AppSettings
from armar_server.contracts import (
    InstanceState,
    InstanceSummary,
    LifecycleEvent,
    LogEvent,
    SseEventType,
    StatusView,
)
from armar_server.server.runtime import PodmanRuntime

from ..logstream import LogLine, LogStreamer
from ..security import get_token_dep

router = APIRouter(prefix="/api/v1/instances", tags=["logs"])


def _settings_for(request: Request, slug: str):
    base: AppSettings = request.app.state.app_settings
    try:
        return InstanceRegistry(base).show(slug), base
    except InstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/{slug}/status", response_model=StatusView)
def get_status(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> StatusView:
    settings, base = _settings_for(request, slug)
    runtime = PodmanRuntime(selinux_relabel=True, userns_keep_id=True)
    is_running = runtime.is_running(settings.container_name)
    last_line = None
    with contextlib.suppress(Exception):
        # Best-effort last log line probe.
        import subprocess

        result = subprocess.run(  # noqa: S603 — fixed argv
            [base.runtime, "logs", "--tail", "1", settings.container_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.stdout.strip():
            last_line = result.stdout.strip().splitlines()[-1]
    summary = InstanceSummary(
        slug=settings.slug,
        name=settings.name,
        state=InstanceState.RUNNING if is_running else InstanceState.STOPPED,
        game_port=settings.game_port,
        a2s_port=settings.a2s_port,
        rcon_port=settings.rcon_port,
        created_at=settings_created_at_fallback(),
    )
    return StatusView(
        instance=summary,
        container_running=is_running,
        last_log_line=last_line,
    )


def settings_created_at_fallback():  # type: ignore[no-untyped-def]
    from datetime import UTC, datetime

    return datetime.fromtimestamp(0, tz=UTC)


@router.get("/{slug}/logs/stream")
async def stream_logs(
    slug: str,
    request: Request,
    tail: int = 50,
    _token: Annotated[None, Depends(get_token_dep)] = None,
) -> EventSourceResponse:
    """Stream `podman logs -f` events for the instance's container."""
    settings, base = _settings_for(request, slug)
    runtime = PodmanRuntime(selinux_relabel=True, userns_keep_id=True)
    if not runtime.is_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"runtime {base.runtime!r} not on PATH"
        )

    streamer = LogStreamer(runtime_binary=base.runtime)
    seq = 0

    async def _gen():  # type: ignore[no-untyped-def]
        nonlocal seq
        # First, seed with `tail` lines from `podman logs --tail`.
        try:
            proc = await asyncio.create_subprocess_exec(
                base.runtime,
                "logs",
                "--tail",
                str(tail),
                settings.container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            assert proc.stdout is not None  # noqa: S101 — type narrowing
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    break
                seq += 1
                line_text = raw.decode("utf-8", errors="replace").rstrip("\n")
                evt = LifecycleEvent(
                    seq=seq,
                    type=SseEventType.LOG,
                    log=LogEvent(
                        seq=seq,
                        ts=asyncio.get_event_loop().time(),  # type: ignore[arg-type]
                        line=line_text,
                    ),
                )
                yield {"id": str(seq), "event": "log", "data": evt.model_dump_json()}
        except Exception as exc:
            yield {
                "event": "error",
                "data": f'{{"error":"seed failed: {exc}"}}',
            }
            return

        # Then, fan out the live `podman logs -f`.
        try:
            async for line in streamer.stream(settings.container_name):
                seq += 1
                evt = LifecycleEvent(
                    seq=seq,
                    type=SseEventType.LOG,
                    log=LogEvent(
                        seq=seq,
                        ts=asyncio.get_event_loop().time(),  # type: ignore[arg-type]
                        line=line.line,
                    ),
                )
                yield {"id": str(seq), "event": "log", "data": evt.model_dump_json()}
        except asyncio.CancelledError:
            return

    return EventSourceResponse(_gen(), ping=15)


__all__ = ["router"]


# Silence unused-import for LogLine (kept for clarity in the module).
_ = LogLine
