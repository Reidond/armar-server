"""Instance CRUD routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from armar_server.config.instance import InstanceSettings, validate_slug
from armar_server.config.registry import (
    InstanceAlreadyExistsError,
    InstanceNotFoundError,
    InstanceRegistry,
    InstanceRunningError,
)
from armar_server.config.settings import AppSettings
from armar_server.contracts import (
    InstanceCreate,
    InstanceDetail,
    InstanceState,
    InstanceSummary,
)

from ..security import get_token_dep

router = APIRouter(prefix="/api/v1/instances", tags=["instances"])


def _registry(request: Request) -> InstanceRegistry:
    base: AppSettings = request.app.state.app_settings
    return InstanceRegistry(base)


def _to_summary(settings: InstanceSettings) -> InstanceSummary:
    return InstanceSummary(
        slug=settings.slug,
        name=settings.name,
        state=InstanceState.STOPPED,
        game_port=settings.game_port,
        a2s_port=settings.a2s_port,
        rcon_port=settings.rcon_port,
        created_at=settings_created_at(settings),
    )


def settings_created_at(_settings: InstanceSettings):  # type: ignore[no-untyped-def]
    """Best-effort created_at lookup; falls back to epoch if missing."""
    from datetime import UTC, datetime

    return datetime.fromtimestamp(0, tz=UTC)


@router.get("", response_model=list[InstanceSummary])
def list_instances(
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> list[InstanceSummary]:
    return [
        _to_summary(InstanceRegistry(request.app.state.app_settings).show(m.slug))
        for m in InstanceRegistry(request.app.state.app_settings).list()
    ]


@router.post("", response_model=InstanceDetail, status_code=status.HTTP_201_CREATED)
def create_instance(
    payload: InstanceCreate,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> InstanceDetail:
    base: AppSettings = request.app.state.app_settings
    registry = InstanceRegistry(base)
    slug = payload.slug or _auto_slug(payload.name, registry)
    try:
        validate_slug(slug)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    try:
        settings = registry.create(
            slug=slug,
            name=payload.name,
            network_mode="host",
            game_port=payload.game_port,
            a2s_port=payload.a2s_port,
            rcon_port=payload.rcon_port,
        )
    except InstanceAlreadyExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return InstanceDetail(
        slug=settings.slug,
        name=settings.name,
        game_port=settings.game_port,
        a2s_port=settings.a2s_port,
        rcon_port=settings.rcon_port,
        created_at=settings_created_at(settings),
        container_name=settings.container_name,
        server_dir=str(settings.server_dir),
        profile_dir=str(settings.profile_dir),
        config_dir=str(settings.config_dir),
        network_mode=settings.network_mode,
    )


@router.get("/{slug}", response_model=InstanceDetail)
def get_instance(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> InstanceDetail:
    base: AppSettings = request.app.state.app_settings
    registry = InstanceRegistry(base)
    try:
        settings = registry.show(slug)
    except InstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return InstanceDetail(
        slug=settings.slug,
        name=settings.name,
        game_port=settings.game_port,
        a2s_port=settings.a2s_port,
        rcon_port=settings.rcon_port,
        created_at=settings_created_at(settings),
        container_name=settings.container_name,
        server_dir=str(settings.server_dir),
        profile_dir=str(settings.profile_dir),
        config_dir=str(settings.config_dir),
        network_mode=settings.network_mode,
    )


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_instance(
    slug: str,
    request: Request,
    force: bool = False,
    _token: Annotated[None, Depends(get_token_dep)] = None,
) -> None:
    base: AppSettings = request.app.state.app_settings
    registry = InstanceRegistry(base)
    try:
        registry.remove(slug, running=force)
    except InstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except InstanceRunningError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


def _auto_slug(name: str, registry: InstanceRegistry) -> str:
    """Generate a slug from ``name`` and ensure it is unique in the registry."""
    base = "".join(c if c.isalnum() or c == "-" else "-" for c in name.lower()).strip("-")
    base = "-".join(p for p in base.split("-") if p)
    if not base:
        base = "instance"
    candidate = base
    n = 1
    while True:
        try:
            validate_slug(candidate)
        except ValueError:
            candidate = f"{base}-{n}"
            n += 1
            continue
        if (registry.instances_dir / candidate).exists():
            candidate = f"{base}-{n}"
            n += 1
            continue
        return candidate
