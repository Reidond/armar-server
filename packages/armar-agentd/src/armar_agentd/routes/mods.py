"""Mods CRUD + resolve (job) routes."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from armar_server.config.loader import load_app_config, save_app_config, save_lock
from armar_server.config.models import LockEntry, LockFile
from armar_server.config.registry import InstanceNotFoundError, InstanceRegistry
from armar_server.config.settings import AppSettings
from armar_server.contracts import JobRef
from armar_server.workshop.client import WORKSHOP_BASE_URL, HttpWorkshopClient, parse_mod_id
from armar_server.workshop.resolver import DependencyResolver

from ..jobs import JobContext
from ..security import get_token_dep

router = APIRouter(prefix="/api/v1/instances", tags=["mods"])


def _settings_for(request: Request, slug: str):
    base: AppSettings = request.app.state.app_settings
    try:
        return InstanceRegistry(base).show(slug), base
    except InstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/{slug}/mods")
def list_mods(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> list[str]:
    settings, _ = _settings_for(request, slug)
    config_path = settings.config_dir.parent / "server.toml"
    if not config_path.exists():
        return []
    return load_app_config(config_path).mods


_MODS_BODY = Body(..., embed=True)


@router.post("/{slug}/mods", status_code=status.HTTP_201_CREATED)
def add_mods(
    slug: str,
    request: Request,
    refs: list[str] = _MODS_BODY,
    _token: Annotated[None, Depends(get_token_dep)] = None,
) -> list[str]:
    settings, _ = _settings_for(request, slug)
    config_path = settings.config_dir.parent / "server.toml"
    cfg = load_app_config(config_path)
    existing = {parse_mod_id(r) for r in cfg.mods}
    for ref in refs:
        mod_id = parse_mod_id(ref)
        if mod_id in existing:
            continue
        cfg.mods.append(f"{WORKSHOP_BASE_URL}{mod_id}")
    save_app_config(config_path, cfg)
    return cfg.mods


@router.delete("/{slug}/mods/{mod_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_mod(
    slug: str,
    mod_id: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> None:
    settings, _ = _settings_for(request, slug)
    config_path = settings.config_dir.parent / "server.toml"
    cfg = load_app_config(config_path)
    before = len(cfg.mods)
    cfg.mods = [r for r in cfg.mods if parse_mod_id(r).upper() != mod_id.upper()]
    if len(cfg.mods) == before:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"mod {mod_id!r} not in instance")
    save_app_config(config_path, cfg)


@router.post("/{slug}/resolve", response_model=JobRef, status_code=status.HTTP_202_ACCEPTED)
async def resolve(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> JobRef:
    settings, _ = _settings_for(request, slug)
    config_path = settings.config_dir.parent / "server.toml"
    lock_path = settings.config_dir.parent / "armar.lock"

    async def _run(ctx: JobContext) -> None:
        cfg = load_app_config(config_path)
        if not cfg.mods:
            raise RuntimeError("no mods configured")
        ids = [parse_mod_id(r) for r in cfg.mods]
        with HttpWorkshopClient() as client:
            result = await asyncio.to_thread(lambda: DependencyResolver(client).resolve(ids))
        lock = LockFile(
            game_version=result.game_version,
            mods=[
                LockEntry(mod_id=m.mod_id, name=m.name, version=m.version, direct=m.direct)
                for m in result.mods
            ],
        )
        save_lock(lock_path, lock)

    job_id = await request.app.state.job_manager.start(_run, kind="resolve", instance_slug=slug)
    return JobRef(job_id=job_id)
