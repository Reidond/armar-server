"""Long-running job management with per-instance locks and SSE event streams.

Each ``install`` / ``update`` / ``up`` / ``resolve`` / etc. is a *job*:
- bounded by a per-instance single-slot lock (one at a time per instance)
- bounded by a global concurrency cap
- bounded by a wall-clock timeout
- emits state / log / progress / result / error / end events with monotonic
  sequence ids; consumers can resume via ``Last-Event-ID``.

A job holds a *process group* (not a single PID) so cancellation can kill
all descendants spawned by the underlying CLI (podman, steamcmd, …).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from armar_server.contracts import (
    JobState,
    LifecycleEvent,
    LogEvent,
    ProgressEvent,
    SseEventType,
)

JobRunner = Callable[["JobContext"], Awaitable[None]]


class JobError(RuntimeError):
    """Raised by the JobManager for invalid state transitions."""


@dataclass
class JobContext:
    """A running job's context, passed to the runner."""

    job_id: str
    instance_slug: str | None
    kind: str
    emit: Callable[[LifecycleEvent], None]


@dataclass
class _RingBuffer:
    """Bounded ring buffer of (seq, LifecycleEvent) for SSE replay."""

    capacity: int
    items: list[tuple[int, LifecycleEvent]] = field(default_factory=list)

    def append(self, seq: int, event: LifecycleEvent) -> None:
        self.items.append((seq, event))
        if len(self.items) > self.capacity:
            self.items = self.items[-self.capacity :]

    def since(self, last_event_id: int) -> list[tuple[int, LifecycleEvent]]:
        return [item for item in self.items if item[0] > last_event_id]


@dataclass
class _Job:
    job_id: str
    state: JobState = JobState.QUEUED
    kind: str = ""
    instance_slug: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    process: asyncio.subprocess.Process | None = None
    seq: int = 0
    events: _RingBuffer = field(default_factory=lambda: _RingBuffer(capacity=1024))
    task: asyncio.Task[None] | None = None
    waiters: list[asyncio.Queue[tuple[int, LifecycleEvent]]] = field(default_factory=list)

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq


class JobManager:
    """Owns all jobs: per-instance locks, timeouts, SSE replay."""

    def __init__(
        self,
        *,
        global_concurrency: int = 2,
        default_timeout_s: float = 60 * 60,
    ) -> None:
        self._jobs: dict[str, _Job] = {}
        self._instance_locks: dict[str, asyncio.Lock] = {}
        self._global_sem = asyncio.Semaphore(global_concurrency)
        self._default_timeout_s = default_timeout_s

    # --- public API ----------------------------------------------------

    def get(self, job_id: str) -> _Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobError(f"job {job_id!r} not found")
        return job

    def view(self, job_id: str) -> dict[str, Any]:
        job = self.get(job_id)
        return {
            "job_id": job.job_id,
            "state": int(job.state),
            "kind": job.kind,
            "instance_slug": job.instance_slug,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "error": job.error,
        }

    def list_jobs(self) -> list[dict[str, Any]]:
        return [self.view(j.job_id) for j in self._jobs.values()]

    async def start(
        self,
        runner: JobRunner,
        *,
        kind: str,
        instance_slug: str | None = None,
        timeout_s: float | None = None,
    ) -> str:
        """Submit a new job. Acquires the per-instance + global lock."""
        if instance_slug is not None:
            lock = self._instance_locks.setdefault(instance_slug, asyncio.Lock())
            if lock.locked():
                raise JobError(f"another job is already running for instance {instance_slug!r}")
        job_id = uuid.uuid4().hex
        job = _Job(job_id=job_id, kind=kind, instance_slug=instance_slug)
        self._jobs[job_id] = job
        job.task = asyncio.create_task(
            self._run(job, runner, timeout_s=timeout_s or self._default_timeout_s),
            name=f"job-{job_id}",
        )
        return job_id

    async def cancel(self, job_id: str) -> None:
        job = self.get(job_id)
        if job.state not in {JobState.QUEUED, JobState.RUNNING}:
            return
        proc = job.process
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGTERM)
        job.state = JobState.CANCELLED
        job.finished_at = _now()
        self._emit(
            job,
            LifecycleEvent(seq=job.next_seq(), type=SseEventType.STATE, error="cancelled"),
        )
        self._emit(job, LifecycleEvent(seq=job.next_seq(), type=SseEventType.END))

    async def events_since(
        self, job_id: str, last_event_id: int = 0
    ) -> list[tuple[int, LifecycleEvent]]:
        job = self.get(job_id)
        return list(job.events.since(last_event_id))

    async def stream(
        self, job_id: str, last_event_id: int = 0
    ) -> AsyncIterator[tuple[int, LifecycleEvent]]:
        job = self.get(job_id)
        for seq, event in job.events.since(last_event_id):
            yield seq, event
        if job.state in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}:
            return
        # Subscribe to live events
        queue: asyncio.Queue[tuple[int, LifecycleEvent]] = asyncio.Queue()
        job.waiters.append(queue)
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    # Heartbeat
                    yield -1, LifecycleEvent(seq=-1, type=SseEventType.STATE)  # heartbeat
                    continue
                yield item
                if item[1].type == SseEventType.END:
                    return
        finally:
            with contextlib.suppress(ValueError):
                job.waiters.remove(queue)

    # --- internals -----------------------------------------------------

    async def _run(
        self,
        job: _Job,
        runner: JobRunner,
        *,
        timeout_s: float,
    ) -> None:
        lock = self._instance_locks[job.instance_slug] if job.instance_slug is not None else None
        try:
            if lock is not None:
                await lock.acquire()
            await self._global_sem.acquire()
            job.state = JobState.RUNNING
            job.started_at = _now()
            self._emit(job, LifecycleEvent(seq=job.next_seq(), type=SseEventType.STATE))
            await asyncio.wait_for(
                runner(
                    JobContext(
                        job_id=job.job_id,
                        instance_slug=job.instance_slug,
                        kind=job.kind,
                        emit=lambda event: self._emit(job, event),
                    )
                ),
                timeout=timeout_s,
            )
            job.state = JobState.SUCCEEDED
            self._emit(
                job,
                LifecycleEvent(seq=job.next_seq(), type=SseEventType.RESULT, result="ok"),
            )
        except TimeoutError as exc:
            job.state = JobState.FAILED
            job.error = f"timeout after {timeout_s}s"
            self._emit(
                job,
                LifecycleEvent(seq=job.next_seq(), type=SseEventType.ERROR, error=str(exc)),
            )
        except asyncio.CancelledError:
            job.state = JobState.CANCELLED
            self._emit(
                job,
                LifecycleEvent(seq=job.next_seq(), type=SseEventType.STATE, error="cancelled"),
            )
            raise
        except Exception as exc:
            job.state = JobState.FAILED
            job.error = str(exc) or exc.__class__.__name__
            self._emit(
                job,
                LifecycleEvent(seq=job.next_seq(), type=SseEventType.ERROR, error=job.error),
            )
        finally:
            job.finished_at = _now()
            self._emit(job, LifecycleEvent(seq=job.next_seq(), type=SseEventType.END))
            if lock is not None:
                lock.release()
            self._global_sem.release()

    def _emit(self, job: _Job, event: LifecycleEvent) -> None:
        job.events.append(event.seq, event)
        for waiter in job.waiters:
            with contextlib.suppress(asyncio.QueueFull):
                waiter.put_nowait((event.seq, event))


def _now() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "JobContext",
    "JobError",
    "JobManager",
    "JobRunner",
    "JobState",
    "LifecycleEvent",
    "LogEvent",
    "ProgressEvent",
    "SseEventType",
]
