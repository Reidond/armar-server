"""Job introspection + SSE event-stream routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sse_starlette.sse import EventSourceResponse

from armar_server.contracts import JobState, JobView

from ..jobs import JobError, JobManager
from ..security import get_token_dep

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _manager(request: Request) -> JobManager:
    return request.app.state.job_manager


@router.get("", response_model=list[JobView])
def list_jobs(
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> list[JobView]:
    out: list[JobView] = []
    for j in _manager(request).list_jobs():
        out.append(
            JobView(
                job_id=j["job_id"],
                state=JobState(j["state"]),
                kind=j["kind"],
                instance_slug=j["instance_slug"],
                started_at=j["started_at"],
                finished_at=j["finished_at"],
                error=j["error"],
            )
        )
    return out


@router.get("/{job_id}", response_model=JobView)
def get_job(
    job_id: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> JobView:
    try:
        j = _manager(request).view(job_id)
    except JobError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return JobView(
        job_id=j["job_id"],
        state=JobState(j["state"]),
        kind=j["kind"],
        instance_slug=j["instance_slug"],
        started_at=j["started_at"],
        finished_at=j["finished_at"],
        error=j["error"],
    )


@router.post("/{job_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel(
    job_id: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> None:
    try:
        await _manager(request).cancel(job_id)
    except JobError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/{job_id}/events")
async def events(
    job_id: str,
    request: Request,
    last_event_id: int = Query(default=0, alias="lastEventId"),
    _token: Annotated[None, Depends(get_token_dep)] = None,
) -> EventSourceResponse:
    manager = _manager(request)

    async def _gen():  # type: ignore[no-untyped-def]
        try:
            async for seq, event in manager.stream(job_id, last_event_id):
                if seq == -1:
                    yield {"event": "heartbeat", "data": "{}"}
                    continue
                yield {
                    "id": str(seq),
                    "event": event.type.name.lower(),
                    "data": event.model_dump_json(),
                }
        except JobError:
            yield {"event": "error", "data": f'{{"error":"job {job_id!r} not found"}}'}

    return EventSourceResponse(_gen(), ping=15)
