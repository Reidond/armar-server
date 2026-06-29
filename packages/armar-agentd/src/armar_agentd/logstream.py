"""`armar-agentd` log streaming.

Fans a single `podman logs -f` per instance out to N SSE subscribers
(when P2 lands). Stubbed here for P1 so the rest of the code path
type-checks; the actual stream implementation lives in P2.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LogLine:
    stream: str  # "stdout" or "stderr"
    line: str


class LogStreamer:
    """One streamer per (instance_slug, container_name)."""

    def __init__(self, *, runtime_binary: str = "podman") -> None:
        self._binary = runtime_binary

    async def stream(self, container_name: str) -> AsyncIterator[LogLine]:
        """Yield LogLine events from `podman logs -f <container>`."""
        proc = await asyncio.create_subprocess_exec(
            self._binary,
            "logs",
            "-f",
            "--tail",
            "50",
            container_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert proc.stdout is not None and proc.stderr is not None  # noqa: S101 — type narrowing
        # Build asyncio tasks that run the drain *coroutines*.
        stdout_coro = self._drain(proc.stdout, "stdout")
        stderr_coro = self._drain(proc.stderr, "stderr")
        stdout_task: asyncio.Task[None] = asyncio.create_task(_drive(stdout_coro))
        stderr_task: asyncio.Task[None] = asyncio.create_task(_drive(stderr_coro))
        try:
            async for line in _merge_drains(stdout_task, stderr_task):
                yield line
        finally:
            stdout_task.cancel()
            stderr_task.cancel()
            with contextlib.suppress(ProcessLookupError):
                proc.terminate()

    @staticmethod
    async def _drain(stream: asyncio.StreamReader, kind: str) -> AsyncIterator[LogLine]:
        while True:
            raw = await stream.readline()
            if not raw:
                return
            yield LogLine(stream=kind, line=raw.decode("utf-8", errors="replace").rstrip("\n"))


async def _drive(agen: AsyncIterator[LogLine]) -> None:
    """Drive an async generator to completion (raises on first StopAsyncIteration)."""
    async for _ in agen:
        pass


async def _merge_drains(*tasks: asyncio.Task[Any]) -> AsyncIterator[LogLine]:
    """Async-iterate multiple drain-driving tasks as a single merged stream."""
    queues: list[asyncio.Queue[LogLine | None]] = [asyncio.Queue() for _ in tasks]
    _drain_max = 0.05  # seconds

    async def _pump(task: asyncio.Task[Any], q: asyncio.Queue[LogLine | None]) -> None:
        try:
            await task
        except asyncio.CancelledError:
            return
        except Exception:  # drain errors are not fatal to the merge
            return
        finally:
            await q.put(None)

    pumps = [asyncio.create_task(_pump(t, q)) for t, q in zip(tasks, queues, strict=True)]
    pending = len(pumps)
    try:
        while pending > 0:
            for q in queues:
                try:
                    item = q.get_nowait()
                except asyncio.QueueEmpty:
                    continue
                if item is None:
                    pending -= 1
                    continue
                yield item
            await asyncio.sleep(_drain_max)
    finally:
        for pump in pumps:
            pump.cancel()


__all__ = ["LogLine", "LogStreamer"]


# Touch Path so the import isn't dead — used by P2 fan-out (caching streams on disk).
_ = Path
