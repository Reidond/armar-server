"""Identity / capability routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from armar_server import __version__ as armar_core_version
from armar_server.contracts import PROTOCOL_VERSION, AgentInfo
from armar_server.contracts.models import AgentInfo as _AgentInfo  # re-export

from ..security import TokenStore, get_token_dep

router = APIRouter(prefix="/api/v1", tags=["host"])


def _hostname() -> str:
    import socket

    try:
        return socket.gethostname()
    except OSError:
        return "unknown"


@router.get("/info")
def info(
    request: Request,
    _token: None = Depends(get_token_dep),  # type: ignore[arg-type]
) -> AgentInfo:
    started_at: datetime = getattr(request.app.state, "started_at", datetime.now(UTC))
    return _AgentInfo(
        agent_version=armar_core_version,
        protocol_version=PROTOCOL_VERSION,
        hostname=_hostname(),
        started_at=started_at,
    )


@router.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
def readyz(request: Request) -> dict[str, str]:
    """Readiness probe: the agent is ready when its token is provisioned."""
    store: TokenStore = request.app.state.token_store
    return {"status": "ready" if store.exists() else "unprovisioned"}
