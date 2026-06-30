"""Container runtime abstraction (Podman default, Docker alternative).

``ContainerRuntime`` is an injectable Protocol; ``build_run_argv`` is a pure
function so tests can assert the exact argv without ever spawning a container.
Podman and Docker share a compatible CLI surface, so one base class covers both.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..config.settings import AppSettings
from ..errors import ContainerError, RuntimeNotFoundError


@dataclass(frozen=True)
class VolumeMount:
    host: str
    container: str
    read_only: bool = False


@dataclass(frozen=True)
class PortMapping:
    host: int
    container: int
    protocol: str = "udp"


@dataclass
class RunSpec:
    image: str
    command: list[str] = field(default_factory=list)
    name: str | None = None
    volumes: list[VolumeMount] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    ports: list[PortMapping] = field(default_factory=list)
    network: str | None = None  # "host" or None (bridged)
    detach: bool = False
    interactive: bool = False
    tty: bool = False
    remove: bool = False
    workdir: str | None = None


@runtime_checkable
class ContainerRuntime(Protocol):
    @property
    def binary(self) -> str: ...

    def is_available(self) -> bool: ...

    def build_run_argv(self, spec: RunSpec) -> list[str]: ...

    def run(self, spec: RunSpec) -> int: ...

    def build_image(
        self, context_dir: Path, tag: str, *, build_args: dict[str, str] | None = None
    ) -> int: ...

    def stop(self, name: str) -> int: ...

    def remove(self, name: str) -> int: ...

    def logs(self, name: str, *, follow: bool = False) -> int: ...

    def is_running(self, name: str) -> bool: ...


class CliContainerRuntime:
    """Shared Podman/Docker implementation shelling out to a compatible CLI."""

    def __init__(
        self,
        binary: str,
        *,
        selinux_relabel: bool = False,
        userns_keep_id: bool = False,
    ) -> None:
        self._binary = binary
        self._selinux_relabel = selinux_relabel
        self._userns_keep_id = userns_keep_id

    @property
    def binary(self) -> str:
        return self._binary

    def is_available(self) -> bool:
        return shutil.which(self._binary) is not None

    def _volume_arg(self, volume: VolumeMount) -> str:
        opts: list[str] = []
        if volume.read_only:
            opts.append("ro")
        if self._selinux_relabel:
            opts.append("Z")
        suffix = f":{','.join(opts)}" if opts else ""
        return f"{volume.host}:{volume.container}{suffix}"

    def build_run_argv(self, spec: RunSpec) -> list[str]:
        argv = [self._binary, "run"]
        if spec.remove:
            argv.append("--rm")
        if spec.detach:
            argv.append("-d")
        if spec.interactive:
            argv.append("-i")
        if spec.tty:
            argv.append("-t")
        if spec.name:
            argv += ["--name", spec.name]
        if spec.network == "host":
            argv += ["--network", "host"]
        else:
            for port in spec.ports:
                argv += ["-p", f"{port.host}:{port.container}/{port.protocol}"]
        if self._userns_keep_id and self._binary == "podman":
            argv += ["--userns", "keep-id"]
        if spec.workdir:
            argv += ["-w", spec.workdir]
        for key, value in spec.env.items():
            argv += ["-e", f"{key}={value}"]
        for volume in spec.volumes:
            argv += ["-v", self._volume_arg(volume)]
        argv.append(spec.image)
        argv += spec.command
        return argv

    def _ensure_available(self) -> None:
        if not self.is_available():
            raise RuntimeNotFoundError(
                f"Container runtime '{self._binary}' not found on PATH. "
                "Install it or set ARMAR_RUNTIME to an available runtime."
            )

    def _run(self, argv: list[str]) -> int:
        self._ensure_available()
        return subprocess.run(argv, check=False).returncode  # noqa: S603 — argv built by pure builder

    def run(self, spec: RunSpec) -> int:
        return self._run(self.build_run_argv(spec))

    def build_image(
        self, context_dir: Path, tag: str, *, build_args: dict[str, str] | None = None
    ) -> int:
        argv = [self._binary, "build", "-t", tag]
        for key, value in (build_args or {}).items():
            argv += ["--build-arg", f"{key}={value}"]
        argv.append(str(context_dir))
        return self._run(argv)

    def stop(self, name: str) -> int:
        return self._run([self._binary, "stop", name])

    def remove(self, name: str) -> int:
        return self._run([self._binary, "rm", "-f", name])

    def logs(self, name: str, *, follow: bool = False) -> int:
        argv = [self._binary, "logs"]
        if follow:
            argv.append("-f")
        argv.append(name)
        return self._run(argv)

    def is_running(self, name: str) -> bool:
        self._ensure_available()
        result = subprocess.run(  # noqa: S603 — argv is fixed (binary + ps subcommand + name)
            [self._binary, "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return name in result.stdout.split()


class PodmanRuntime(CliContainerRuntime):
    def __init__(self, *, selinux_relabel: bool = True, userns_keep_id: bool = True) -> None:
        super().__init__("podman", selinux_relabel=selinux_relabel, userns_keep_id=userns_keep_id)


class DockerRuntime(CliContainerRuntime):
    def __init__(self) -> None:
        super().__init__("docker", selinux_relabel=False, userns_keep_id=False)


def make_runtime(settings: AppSettings) -> ContainerRuntime:
    if settings.runtime == "docker":
        return DockerRuntime()
    if settings.runtime == "podman":
        return PodmanRuntime(
            selinux_relabel=settings.selinux_relabel,
            userns_keep_id=settings.userns_keep_id,
        )
    raise ContainerError(f"Unknown runtime '{settings.runtime}' (use 'podman' or 'docker').")
