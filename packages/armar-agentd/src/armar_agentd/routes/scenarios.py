"""Scenarios routes (list / network scan)."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from armar_server.config.loader import load_app_config
from armar_server.config.registry import InstanceNotFoundError, InstanceRegistry
from armar_server.config.settings import AppSettings
from armar_server.contracts import JobRef
from armar_server.workshop.client import HttpWorkshopClient, parse_mod_id
from armar_server.workshop.parser import parse_asset

from ..jobs import JobContext
from ..security import get_token_dep

router = APIRouter(prefix="/api/v1/instances", tags=["scenarios"])


def _settings_for(request: Request, slug: str):
    base: AppSettings = request.app.state.app_settings
    try:
        return InstanceRegistry(base).show(slug), base
    except InstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/{slug}/scenarios")
def list_scenarios(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> list[dict[str, object]]:
    settings, _ = _settings_for(request, slug)
    config_path = settings.config_dir.parent / "server.toml"
    cfg = load_app_config(config_path)
    out: list[dict[str, object]] = []
    if not cfg.mods:
        return out
    ids = [parse_mod_id(r) for r in cfg.mods]
    with HttpWorkshopClient() as client:
        for mod_id in ids:
            asset = parse_asset(client.fetch_page(mod_id))
            for s in asset.scenarios:
                out.append({"modId": mod_id, "name": asset.name, "gameId": s.gameId})
    return out


@router.post("/{slug}/scenarios/scan", response_model=JobRef, status_code=status.HTTP_202_ACCEPTED)
async def scan_scenarios(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> JobRef:
    settings, _ = _settings_for(request, slug)
    config_path = settings.config_dir.parent / "server.toml"

    async def _run(ctx: JobContext) -> None:
        cfg = load_app_config(config_path)
        if not cfg.mods:
            raise RuntimeError("no mods configured")
        ids = [parse_mod_id(r) for r in cfg.mods]
        with HttpWorkshopClient() as client:
            await asyncio.to_thread(lambda: [parse_asset(client.fetch_page(m)) for m in ids])

    job_id = await request.app.state.job_manager.start(
        _run, kind="scenarios-scan", instance_slug=slug
    )
    return JobRef(job_id=job_id)
