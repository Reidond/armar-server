"""Multi-server instance model: `InstanceLayout` + `InstanceSettings` + `validate_slug`.

The instance model is the **single most important change** of the
multi-server work. Today `AppSettings` hard-codes
``container_name="armar-reforger"`` and ports ``2001/17777/19999``;
multi-server requires per-instance namespacing under
``instances_dir/<slug>/...``.

- `InstanceLayout` is a `Protocol` that abstracts *where* the instance's
  container, server dir, profile, and config live, plus its ports.
- `InstanceSettings` is the per-instance frozen value object used at
  runtime. It implements `InstanceLayout` and provides a
  `.legacy(base)` factory that reproduces today's cwd layout byte-for-byte
  so a single-server install keeps working unchanged.
- `validate_slug` enforces the slug rules (reserved names, allowed
  characters, length).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .settings import AppSettings

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}[a-z0-9]$")
_RESERVED_SLUGS: frozenset[str] = frozenset({"default", "reforger", "armar"})


def validate_slug(slug: str) -> str:
    """Validate an instance slug. Returns the slug on success; raises ``ValueError``."""
    if not slug or not _SLUG_RE.match(slug):
        raise ValueError(
            f"invalid slug {slug!r}: must be 2-32 chars, lowercase alphanumeric/hyphen, "
            "must start and end with [a-z0-9]"
        )
    if slug in _RESERVED_SLUGS:
        raise ValueError(f"slug {slug!r} is reserved")
    return slug


@runtime_checkable
class InstanceLayout(Protocol):
    """Where the instance's container + files live, and what ports it owns."""

    slug: str
    name: str
    container_name: str
    server_dir: Path
    profile_dir: Path
    config_dir: Path
    game_port: int
    a2s_port: int
    rcon_port: int
    network_mode: str


@dataclass(frozen=True, slots=True)
class InstanceSettings:
    """Per-instance layout: where its files live, what ports it owns.

    Use ``InstanceSettings.legacy(base)`` to reproduce today's cwd layout
    for the *legacy default* instance (no per-instance dir).
    """

    slug: str
    name: str
    container_name: str
    server_dir: Path
    profile_dir: Path
    config_dir: Path
    game_port: int
    a2s_port: int
    rcon_port: int
    network_mode: str = "host"

    @classmethod
    def legacy(cls, base: AppSettings, *, name: str = "armar") -> InstanceSettings:
        """Reproduce today's single-server cwd layout byte-for-byte."""
        return cls(
            slug="default",
            name=name,
            container_name=base.container_name,
            server_dir=base.server_dir,
            profile_dir=base.profile_dir,
            config_dir=base.config_dir,
            game_port=base.game_port,
            a2s_port=base.a2s_port,
            rcon_port=base.rcon_port,
            network_mode=base.network_mode,
        )

    @classmethod
    def from_base(
        cls,
        base: AppSettings,
        *,
        slug: str,
        name: str,
        game_port: int,
        a2s_port: int,
        rcon_port: int,
        network_mode: str = "host",
    ) -> InstanceSettings:
        """Build a per-instance layout under ``instances_dir/<slug>/``.

        Slug ``default`` is reserved and can only be created via
        :py:meth:`legacy` / :py:meth:`InstanceRegistry.adopt_default`.
        """
        if slug != "default":
            validate_slug(slug)
        if network_mode not in {"host", "bridge"}:
            raise ValueError(f"network_mode must be 'host' or 'bridge', got {network_mode!r}")
        root = base.instances_dir / slug
        return cls(
            slug=slug,
            name=name,
            container_name=f"armar-{slug}" if slug != "default" else "armar-reforger",
            server_dir=root / "server",
            profile_dir=root / "profile",
            config_dir=root / "config",
            game_port=game_port,
            a2s_port=a2s_port,
            rcon_port=rcon_port,
            network_mode=network_mode,
        )

    def to_app_settings(self, base: AppSettings) -> AppSettings:
        """Project this layout onto a fresh ``AppSettings`` for the pure builders.

        The launcher / steamcmd / systemd builders still take an
        ``AppSettings`` (their signature is well-tested). This helper
        builds a copy whose per-instance paths override the cwd default.
        """
        return base.model_copy(
            update={
                "data_dir": self.server_dir.parent,
                "config_file": self.config_dir.parent / "server.toml",
                "lock_file": self.config_dir.parent / "armar.lock",
                "container_name": self.container_name,
                "game_port": self.game_port,
                "a2s_port": self.a2s_port,
                "rcon_port": self.rcon_port,
                "network_mode": self.network_mode,
            }
        )


__all__ = [
    "InstanceLayout",
    "InstanceSettings",
    "validate_slug",
]
