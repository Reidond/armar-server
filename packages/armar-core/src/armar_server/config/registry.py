"""On-disk instance registry.

One instance = one subdir under ``instances_dir`` with a ``instance.toml``
manifest. CRUD operations are atomic (temp-write + rename) and serialized
across processes via a file lock (acquired during ``create()``).

Reserved slugs (``default``/``reforger``/``armar``) cannot be used to
prevent collisions with the legacy single-server install.
"""

from __future__ import annotations

import contextlib
import fcntl
import time
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import tomli_w

from .instance import InstanceSettings, validate_slug
from .ports import PortTriplet, allocate_triplet
from .settings import AppSettings

CURRENT_SCHEMA_VERSION = 1


class InstanceError(RuntimeError):
    """Base class for registry errors."""


class InstanceNotFoundError(InstanceError):
    pass


class InstanceAlreadyExistsError(InstanceError):
    pass


class InstanceRunningError(InstanceError):
    """Raised when an operation would mutate a running instance."""


@dataclass(frozen=True, slots=True)
class InstanceManifest:
    """Persisted per-instance state (``instance.toml``)."""

    slug: str
    name: str
    game_port: int
    a2s_port: int
    rcon_port: int
    network_mode: str
    created_at: datetime
    schema_version: int = CURRENT_SCHEMA_VERSION

    def to_toml(self) -> str:
        return tomli_w.dumps(
            {
                "schema_version": self.schema_version,
                "slug": self.slug,
                "name": self.name,
                "game_port": self.game_port,
                "a2s_port": self.a2s_port,
                "rcon_port": self.rcon_port,
                "network_mode": self.network_mode,
                "created_at": self.created_at.isoformat(),
            }
        )

    @classmethod
    def from_toml(cls, text: str) -> InstanceManifest:
        data = tomllib.loads(text)
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            slug=str(data["slug"]),
            name=str(data["name"]),
            game_port=int(data["game_port"]),
            a2s_port=int(data["a2s_port"]),
            rcon_port=int(data["rcon_port"]),
            network_mode=str(data.get("network_mode", "host")),
            created_at=datetime.fromisoformat(str(data["created_at"])),
        )


def _lock_path(instances_dir: Path) -> Path:
    return instances_dir / ".lock"


@contextlib.contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fp:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)


class InstanceRegistry:
    """CRUD over on-disk instance manifests.

    Thread/process safe for ``create()`` (file lock); ``list/show/remove``
    are snapshot reads and may be racy with concurrent ``create()``.
    """

    def __init__(self, base: AppSettings) -> None:
        self._base = base
        self._dir = base.instances_dir

    @property
    def instances_dir(self) -> Path:
        return self._dir

    # --- write ---------------------------------------------------------

    def create(
        self,
        *,
        slug: str,
        name: str,
        network_mode: str = "host",
        game_port: int | None = None,
        a2s_port: int | None = None,
        rcon_port: int | None = None,
    ) -> InstanceSettings:
        """Atomically create a new instance.

        Holds a file lock around the whole transaction: load used ports,
        compute the next free triplet, write the manifest, return the
        settings. If anything fails the lock is released and no files
        are written.
        """
        validate_slug(slug)
        with _file_lock(_lock_path(self._dir)):
            self._dir.mkdir(parents=True, exist_ok=True)
            instance_dir = self._dir / slug
            if instance_dir.exists():
                raise InstanceAlreadyExistsError(f"instance {slug!r} already exists")
            used = self._used_ports_locked()
            if game_port is not None and a2s_port is not None and rcon_port is not None:
                triplet = PortTriplet(game_port, a2s_port, rcon_port)
                if any(p in used for p in (triplet.game, triplet.a2s, triplet.rcon)):
                    raise InstanceError(
                        f"requested triplet {triplet} overlaps with an existing instance"
                    )
            else:
                triplet = allocate_triplet(
                    used,
                    base_game=self._base.game_port,
                    base_a2s=self._base.a2s_port,
                    base_rcon=self._base.rcon_port,
                )
            settings = InstanceSettings.from_base(
                self._base,
                slug=slug,
                name=name,
                game_port=triplet.game,
                a2s_port=triplet.a2s,
                rcon_port=triplet.rcon,
                network_mode=network_mode,
            )
            manifest = InstanceManifest(
                slug=settings.slug,
                name=settings.name,
                game_port=settings.game_port,
                a2s_port=settings.a2s_port,
                rcon_port=settings.rcon_port,
                network_mode=settings.network_mode,
                created_at=datetime.now(UTC),
            )
            instance_dir.mkdir(parents=False, exist_ok=False)
            (instance_dir / "config").mkdir(parents=True, exist_ok=True)
            manifest_path = instance_dir / "instance.toml"
            _atomic_write(manifest_path, manifest.to_toml())
            return settings

    def remove(self, slug: str, *, running: bool = False) -> None:
        """Remove an instance directory.

        Set ``running=True`` if the instance's container is currently
        running (skips safety checks — caller is responsible).
        """
        if not running:
            settings = self.show(slug)
            if not running and self._is_container_running(settings):
                raise InstanceRunningError(
                    f"instance {slug!r} is running; stop it first or pass running=True"
                )
        instance_dir = self._dir / slug
        if not instance_dir.exists():
            raise InstanceNotFoundError(slug)
        import shutil

        shutil.rmtree(instance_dir)

    def adopt_default(self) -> InstanceSettings | None:
        """Migrate the legacy cwd single-server install into the registry.

        Returns the new ``InstanceSettings`` if there was a legacy
        install to adopt, else ``None``. If an instance with slug
        ``default`` already exists, raises ``InstanceAlreadyExistsError``.
        """
        with _file_lock(_lock_path(self._dir)):
            if (self._dir / "default").exists():
                raise InstanceAlreadyExistsError("instance 'default' already exists")
            legacy = InstanceSettings.legacy(self._base)
            if not legacy.server_dir.exists():
                return None
            used = self._used_ports_locked()
            if any(p in used for p in (legacy.game_port, legacy.a2s_port, legacy.rcon_port)):
                # Conflict: the legacy base triplet is already taken by
                # another instance; allocate a fresh one.
                triplet = allocate_triplet(
                    used,
                    base_game=self._base.game_port,
                    base_a2s=self._base.a2s_port,
                    base_rcon=self._base.rcon_port,
                )
                legacy = InstanceSettings.from_base(
                    self._base,
                    slug="default",
                    name=legacy.name,
                    game_port=triplet.game,
                    a2s_port=triplet.a2s,
                    rcon_port=triplet.rcon,
                    network_mode=legacy.network_mode,
                )
            manifest = InstanceManifest(
                slug=legacy.slug,
                name=legacy.name,
                game_port=legacy.game_port,
                a2s_port=legacy.a2s_port,
                rcon_port=legacy.rcon_port,
                network_mode=legacy.network_mode,
                created_at=datetime.now(UTC),
            )
            (self._dir / "default").mkdir(parents=True, exist_ok=False)
            (self._dir / "default" / "config").mkdir(parents=True, exist_ok=True)
            _atomic_write(self._dir / "default" / "instance.toml", manifest.to_toml())
            return legacy

    # --- read ----------------------------------------------------------

    def list(self) -> list[InstanceManifest]:
        if not self._dir.exists():
            return []
        out: list[InstanceManifest] = []
        for path in sorted(self._dir.iterdir()):
            if not path.is_dir() or path.name.startswith("."):
                continue
            manifest_path = path / "instance.toml"
            if not manifest_path.exists():
                continue
            try:
                out.append(InstanceManifest.from_toml(manifest_path.read_text(encoding="utf-8")))
            except (KeyError, ValueError, tomllib.TOMLDecodeError):
                continue
        return out

    def show(self, slug: str) -> InstanceSettings:
        manifest = self._read_manifest(slug)
        return InstanceSettings.from_base(
            self._base,
            slug=manifest.slug,
            name=manifest.name,
            game_port=manifest.game_port,
            a2s_port=manifest.a2s_port,
            rcon_port=manifest.rcon_port,
            network_mode=manifest.network_mode,
        )

    # --- helpers -------------------------------------------------------

    def _read_manifest(self, slug: str) -> InstanceManifest:
        manifest_path = self._dir / slug / "instance.toml"
        if not manifest_path.exists():
            raise InstanceNotFoundError(slug)
        return InstanceManifest.from_toml(manifest_path.read_text(encoding="utf-8"))

    def _used_ports_locked(self) -> set[int]:
        used: set[int] = set()
        for manifest in self.list():
            used.update({manifest.game_port, manifest.a2s_port, manifest.rcon_port})
        return used

    def _is_container_running(self, settings: InstanceSettings) -> bool:
        """Best-effort probe; uses the configured container runtime."""
        import shutil
        import subprocess

        binary = self._base.runtime
        if not shutil.which(binary):
            return False
        try:
            result = subprocess.run(  # noqa: S603 — argv is fixed (binary + ps subcommand + name)
                [
                    binary,
                    "ps",
                    "--filter",
                    f"name=^{settings.container_name}$",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            return False
        return settings.container_name in result.stdout.split()


def _atomic_write(path: Path, data: str) -> None:
    """Write atomically: temp file + fsync + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{int(time.time() * 1_000_000)}")
    try:
        with tmp.open("w", encoding="utf-8") as fp:
            fp.write(data)
            fp.flush()
            import os

            os.fsync(fp.fileno())
        tmp.replace(path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "InstanceAlreadyExistsError",
    "InstanceError",
    "InstanceManifest",
    "InstanceNotFoundError",
    "InstanceRegistry",
    "InstanceRunningError",
]
