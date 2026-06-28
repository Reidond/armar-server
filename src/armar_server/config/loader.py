"""Read/write of ``server.toml`` and ``armar.lock``, plus JSON config rendering."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import tomli_w
from pydantic import ValidationError

from ..errors import ConfigError
from .models import AppConfig, LockFile, ServerConfig


def load_app_config(path: Path) -> AppConfig:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}. Run `armar init` first.")
    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in {path}: {e}") from e
    section = raw.get("server", raw)
    try:
        return AppConfig.model_validate(section)
    except ValidationError as e:
        raise ConfigError(f"Invalid configuration in {path}:\n{e}") from e


def save_app_config(path: Path, cfg: AppConfig) -> None:
    """Persist config under a ``[server]`` table. Normalizes formatting/comments."""
    data = {"server": cfg.model_dump(mode="json", exclude_none=True)}
    with path.open("wb") as fh:
        tomli_w.dump(data, fh)


def load_lock(path: Path) -> LockFile:
    if not path.exists():
        raise ConfigError(f"Lock file not found: {path}. Run `armar resolve` first.")
    try:
        return LockFile.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as e:
        raise ConfigError(f"Invalid lock file {path}:\n{e}") from e


def save_lock(path: Path, lock: LockFile) -> None:
    payload = lock.model_dump(mode="json", exclude_none=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def render_server_config(cfg: ServerConfig) -> str:
    """Serialize a ``ServerConfig`` to the JSON the server expects via ``-config``."""
    data = cfg.model_dump(exclude_none=True)
    if not data.get("operating"):
        data.pop("operating", None)
    return json.dumps(data, indent=2) + "\n"
