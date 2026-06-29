"""HTTP+SSE implementation of `AgentClient` using httpx.

The local connection (UDS) and the remote connection (over the SSH
local-forward) both speak the same `armar-agentd` HTTP API, so they
share this client — the only difference is the transport.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

import httpx

from armar_server.contracts import (
    AgentInfo,
    AppConfigUpdate,
    AppConfigView,
    InstanceCreate,
    InstanceDetail,
    InstanceSummary,
    JobRef,
    JobView,
    LifecycleEvent,
    SseEventType,
    StatusView,
)

from .client import AgentClient


class HttpAgentClient(AgentClient):
    """HTTP+SSE client for `armar-agentd` (works for both local and remote)."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            transport=transport,
            base_url=self._base_url,
            headers=headers,
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _url(self, path: str) -> str:
        return urljoin(self._base_url, path.lstrip("/"))

    async def _get_json(self, path: str) -> dict[str, Any]:
        r = await self._client.get(self._url(path))
        r.raise_for_status()
        result: dict[str, Any] = r.json()
        return result

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        r = await self._client.post(self._url(path), json=body or {})
        r.raise_for_status()
        return r

    async def _put_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        r = await self._client.put(self._url(path), json=body)
        r.raise_for_status()
        result: dict[str, Any] = r.json()
        return result

    async def _delete(self, path: str) -> None:
        r = await self._client.delete(self._url(path))
        r.raise_for_status()

    # --- identity / instances ---------------------------------------

    async def info(self) -> AgentInfo:
        data = await self._get_json("api/v1/info")
        return AgentInfo.model_validate(data)

    async def list_instances(self) -> list[InstanceSummary]:
        data = await self._get_json("api/v1/instances")
        return [InstanceSummary.model_validate(item) for item in data]

    async def create_instance(self, payload: InstanceCreate) -> InstanceDetail:
        r = await self._post("api/v1/instances", payload.model_dump(exclude_none=True))
        return InstanceDetail.model_validate(r.json())

    async def get_instance(self, slug: str) -> InstanceDetail:
        data = await self._get_json(f"api/v1/instances/{slug}")
        return InstanceDetail.model_validate(data)

    async def delete_instance(self, slug: str, *, force: bool = False) -> None:
        await self._delete(f"api/v1/instances/{slug}?force={'true' if force else 'false'}")

    # --- lifecycle ---------------------------------------------------

    async def install(self, slug: str, *, no_validate: bool = False) -> JobRef:
        r = await self._post(f"api/v1/instances/{slug}/install", {"no_validate": no_validate})
        return JobRef.model_validate(r.json())

    async def up(self, slug: str) -> JobRef:
        r = await self._post(f"api/v1/instances/{slug}/up")
        return JobRef.model_validate(r.json())

    async def stop(self, slug: str) -> JobRef:
        r = await self._post(f"api/v1/instances/{slug}/stop")
        return JobRef.model_validate(r.json())

    async def restart(self, slug: str) -> JobRef:
        r = await self._post(f"api/v1/instances/{slug}/restart")
        return JobRef.model_validate(r.json())

    async def resolve(self, slug: str) -> JobRef:
        r = await self._post(f"api/v1/instances/{slug}/resolve")
        return JobRef.model_validate(r.json())

    # --- jobs --------------------------------------------------------

    async def list_jobs(self) -> list[JobView]:
        data = await self._get_json("api/v1/jobs")
        return [JobView.model_validate(item) for item in data]

    async def cancel_job(self, job_id: str) -> None:
        await self._post(f"api/v1/jobs/{job_id}/cancel")

    async def job_events(  # type: ignore[override]
        self, job_id: str, last_event_id: int = 0
    ):
        url = self._url(f"api/v1/jobs/{job_id}/events")
        headers = {"Accept": "text/event-stream"}
        if last_event_id:
            headers["Last-Event-ID"] = str(last_event_id)
        async with self._client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            event_data: list[str] = []
            event_id: int | None = None
            event_type = "message"
            async for line in response.aiter_lines():
                if not line:
                    if not event_data:
                        continue
                    payload = "\n".join(event_data)
                    if event_type == "heartbeat":
                        event_data.clear()
                        event_id = None
                        event_type = "message"
                        continue
                    try:
                        data = json.loads(payload) if payload else {}
                    except json.JSONDecodeError:
                        data = {}
                    yield LifecycleEvent.model_validate(
                        {
                            "seq": event_id or 0,
                            "type": _sse_type(event_type),
                            **{k: v for k, v in data.items() if k != "seq" and k != "type"},
                        }
                    )
                    event_data.clear()
                    event_id = None
                    event_type = "message"
                    continue
                if line.startswith(":"):
                    continue
                if ":" in line:
                    field, _, value = line.partition(":")
                    value = value.lstrip(" ")
                else:
                    field, value = line, ""
                if field == "id":
                    try:
                        event_id = int(value)
                    except ValueError:
                        event_id = None
                elif field == "event":
                    event_type = value
                elif field == "data":
                    event_data.append(value)

    # --- status / config ---------------------------------------------

    async def get_status(self, slug: str) -> StatusView:
        data = await self._get_json(f"api/v1/instances/{slug}/status")
        return StatusView.model_validate(data)

    async def get_config(self, slug: str) -> AppConfigView:
        data = await self._get_json(f"api/v1/instances/{slug}/config")
        return AppConfigView.model_validate(data)

    async def put_config(self, slug: str, payload: AppConfigUpdate) -> AppConfigView:
        data = await self._put_json(
            f"api/v1/instances/{slug}/config",
            payload.model_dump(exclude_none=True),
        )
        return AppConfigView.model_validate(data)


def _sse_type(name: str) -> SseEventType:
    name = name.lower()
    return {
        "state": SseEventType.STATE,
        "log": SseEventType.LOG,
        "progress": SseEventType.PROGRESS,
        "result": SseEventType.RESULT,
        "error": SseEventType.ERROR,
        "end": SseEventType.END,
    }.get(name, SseEventType.STATE)


__all__ = ["HttpAgentClient"]


# LocalConnection reuses HttpAgentClient with a UDS transport.
class LocalConnection(HttpAgentClient):
    """Loopback/UDS connection to the local `armar-agentd` (no token)."""

    def __init__(self, *, uds_path: str) -> None:
        transport = httpx.AsyncHTTPTransport(uds=uds_path)
        super().__init__(base_url="http://localhost/", token=None, transport=transport)
