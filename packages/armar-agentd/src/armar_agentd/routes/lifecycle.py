"""Lifecycle routes (install / update / up / stop / restart)."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, status

from armar_server.config.instance import InstanceSettings
from armar_server.config.loader import load_app_config, render_server_config
from armar_server.config.registry import InstanceNotFoundError, InstanceRegistry
from armar_server.config.settings import AppSettings
from armar_server.contracts import JobRef
from armar_server.net import detect_lan_ip
from armar_server.server.config_builder import build_server_config
from armar_server.server.launcher import build_server_spec, build_steamcmd_spec
from armar_server.server.runtime import PodmanRuntime

from ..jobs import JobContext, JobManager
from ..security import get_token_dep

router = APIRouter(prefix="/api/v1/instances", tags=["lifecycle"])


def _manager(request: Request) -> JobManager:
    return request.app.state.job_manager


def _runtime_for(_base: AppSettings) -> PodmanRuntime:
    return PodmanRuntime(selinux_relabel=True, userns_keep_id=True)


def _resolve(request: Request, slug: str) -> tuple[AppSettings, InstanceSettings]:
    base: AppSettings = request.app.state.app_settings
    try:
        inst = InstanceRegistry(base).show(slug)
    except InstanceNotFoundError as exc:
        from fastapi import HTTPException

        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return base, inst


@router.post("/{slug}/install", response_model=JobRef, status_code=status.HTTP_202_ACCEPTED)
async def install(
    slug: str,
    request: Request,
    no_validate: bool = Body(default=False, embed=True),
    _token: Annotated[None, Depends(get_token_dep)] = None,
) -> JobRef:
    base, settings = _resolve(request, slug)

    async def _run(ctx: JobContext) -> None:
        runtime = _runtime_for(base)
        # Build the per-instance AppSettings projection.
        per_instance = settings.to_app_settings(base)
        per_instance.server_dir.mkdir(parents=True, exist_ok=True)
        spec = build_steamcmd_spec(per_instance, validate=not no_validate)
        await asyncio.to_thread(runtime.run, spec)

    job_id = await _manager(request).start(_run, kind="install", instance_slug=slug)
    return JobRef(job_id=job_id)


@router.post("/{slug}/up", response_model=JobRef, status_code=status.HTTP_202_ACCEPTED)
async def up(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)] = None,
) -> JobRef:
    base, settings = _resolve(request, slug)

    async def _run(ctx: JobContext) -> None:
        from pathlib import Path

        runtime = _runtime_for(base)
        per_instance = settings.to_app_settings(base)
        config_path = per_instance.config_file
        if not config_path.exists():
            raise RuntimeError(f"no server.toml at {config_path}")
        cfg = load_app_config(config_path)
        from armar_server.config.loader import load_lock
        from armar_server.config.models import LockFile

        lock_path = per_instance.lock_file
        lock: LockFile = load_lock(lock_path) if lock_path.exists() else LockFile()
        public = cfg.public_address or detect_lan_ip()
        server_cfg = build_server_config(cfg, lock, public_address=public)
        rendered_path = Path(per_instance.rendered_config_path)
        rendered_path.parent.mkdir(parents=True, exist_ok=True)
        rendered_path.write_text(render_server_config(server_cfg), encoding="utf-8")
        await asyncio.to_thread(runtime.remove, settings.container_name)
        spec = build_server_spec(per_instance, cfg, detach=True)
        await asyncio.to_thread(runtime.run, spec)

    job_id = await _manager(request).start(_run, kind="up", instance_slug=slug)
    return JobRef(job_id=job_id)


@router.post("/{slug}/stop", response_model=JobRef, status_code=status.HTTP_202_ACCEPTED)
async def stop(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)] = None,
) -> JobRef:
    base, settings = _resolve(request, slug)

    async def _run(ctx: JobContext) -> None:
        runtime = _runtime_for(base)
        await asyncio.to_thread(runtime.stop, settings.container_name)

    job_id = await _manager(request).start(_run, kind="stop", instance_slug=slug)
    return JobRef(job_id=job_id)


@router.post("/{slug}/restart", response_model=JobRef, status_code=status.HTTP_202_ACCEPTED)
async def restart(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)] = None,
) -> JobRef:
    base, settings = _resolve(request, slug)

    async def _run(ctx: JobContext) -> None:
        runtime = _runtime_for(base)
        with contextlib.suppress(Exception):
            await asyncio.to_thread(runtime.stop, settings.container_name)
        await asyncio.to_thread(runtime.remove, settings.container_name)

    job_id = await _manager(request).start(_run, kind="restart", instance_slug=slug)
    return JobRef(job_id=job_id)
