"""AppConfig GET/PUT + render routes (secrets masked)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import SecretStr

from armar_server.config.loader import (
    load_app_config,
    render_server_config,
    save_app_config,
)
from armar_server.config.models import ServerConfig
from armar_server.config.registry import InstanceNotFoundError, InstanceRegistry
from armar_server.config.settings import AppSettings
from armar_server.contracts import AppConfigUpdate, AppConfigView
from armar_server.server.config_builder import build_server_config

from ..security import get_token_dep

router = APIRouter(prefix="/api/v1/instances", tags=["config"])

_SECRET_KEYS = frozenset({"password", "admin_password", "rcon_password"})


def _settings_for(request: Request, slug: str):
    base: AppSettings = request.app.state.app_settings
    try:
        return InstanceRegistry(base).show(slug), base
    except InstanceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/{slug}/config", response_model=AppConfigView)
def get_config(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> AppConfigView:
    settings, _ = _settings_for(request, slug)
    config_path = settings.config_dir.parent / "server.toml"
    if not config_path.exists():
        return AppConfigView(raw={}, secrets={})
    cfg = load_app_config(config_path)
    raw = cfg.model_dump()
    secrets: dict[str, dict[str, bool]] = {
        key: {"set": True} for key in _SECRET_KEYS if raw.get(key)
    }
    for key in _SECRET_KEYS:
        raw.pop(key, None)
    return AppConfigView.model_validate({"raw": raw, "secrets": secrets})


@router.put("/{slug}/config", response_model=AppConfigView)
def put_config(
    slug: str,
    request: Request,
    payload: AppConfigUpdate,
    _token: Annotated[None, Depends(get_token_dep)] = None,
) -> AppConfigView:
    settings, _ = _settings_for(request, slug)
    config_path = settings.config_dir.parent / "server.toml"
    cfg = load_app_config(config_path) if config_path.exists() else None
    if cfg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no server.toml to update")
    # Apply non-secret fields.
    for key, value in payload.raw.items():
        if key in _SECRET_KEYS:
            continue  # write-only via secrets
        setattr(cfg, key, value)
    # fastValidation must stay true for public servers.
    if "fastValidation" in payload.raw and payload.raw["fastValidation"] is False:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "fastValidation must stay true for a public server",
        )
    # Apply secrets: SecretStr replaces; None clears.
    for key, value in (payload.secrets or {}).items():
        if key not in _SECRET_KEYS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{key!r} is not a recognised secret")
        if value is None:
            setattr(cfg, key, "")
        else:
            assert isinstance(value, SecretStr)  # noqa: S101 — pydantic guarantees this
            setattr(cfg, key, value.get_secret_value())
    save_app_config(config_path, cfg)
    return get_config(slug, request, _token)  # type: ignore[arg-type]


@router.get("/{slug}/render")
def render(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> dict[str, object]:
    settings, _ = _settings_for(request, slug)
    from armar_server.config.loader import load_lock
    from armar_server.config.models import LockFile

    config_path = settings.config_dir.parent / "server.toml"
    lock_path = settings.config_dir.parent / "armar.lock"
    cfg = load_app_config(config_path)
    lock: LockFile = load_lock(lock_path) if lock_path.exists() else LockFile()
    server_cfg: ServerConfig = build_server_config(cfg, lock, public_address=cfg.public_address)
    return server_cfg.model_dump(by_alias=True, exclude_none=True)


@router.post("/{slug}/render", status_code=status.HTTP_200_OK)
def write_rendered(
    slug: str,
    request: Request,
    _token: Annotated[None, Depends(get_token_dep)],
) -> dict[str, str]:
    settings, _ = _settings_for(request, slug)
    from armar_server.config.loader import load_lock
    from armar_server.config.models import LockFile

    config_path = settings.config_dir.parent / "server.toml"
    lock_path = settings.config_dir.parent / "armar.lock"
    cfg = load_app_config(config_path)
    lock: LockFile = load_lock(lock_path) if lock_path.exists() else LockFile()
    server_cfg = build_server_config(cfg, lock, public_address=cfg.public_address)
    from pathlib import Path

    rendered_path = Path(settings.config_dir) / "server-config.json"
    rendered_path.parent.mkdir(parents=True, exist_ok=True)
    rendered_path.write_text(render_server_config(server_cfg), encoding="utf-8")
    return {"path": str(rendered_path)}
