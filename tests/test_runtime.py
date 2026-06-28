from __future__ import annotations

import pytest

from armar_server.config.settings import AppSettings
from armar_server.errors import ContainerError
from armar_server.server.runtime import (
    DockerRuntime,
    PodmanRuntime,
    PortMapping,
    RunSpec,
    VolumeMount,
    make_runtime,
)


def test_podman_host_argv() -> None:
    runtime = PodmanRuntime(selinux_relabel=True, userns_keep_id=True)
    spec = RunSpec(
        image="img",
        command=["/server/ArmaReforgerServer", "-config", "x"],
        name="armar",
        network="host",
        volumes=[VolumeMount("/h/s", "/server")],
        remove=True,
        interactive=True,
        tty=True,
        workdir="/server",
    )
    assert runtime.build_run_argv(spec) == [
        "podman", "run", "--rm", "-i", "-t",
        "--name", "armar",
        "--network", "host",
        "--userns", "keep-id",
        "-w", "/server",
        "-v", "/h/s:/server:Z",
        "img",
        "/server/ArmaReforgerServer", "-config", "x",
    ]  # fmt: skip


def test_docker_bridge_argv() -> None:
    runtime = DockerRuntime()
    spec = RunSpec(
        image="img",
        command=["run"],
        ports=[PortMapping(2001, 2001, "udp")],
        volumes=[VolumeMount("/h/s", "/server")],
        remove=True,
    )
    argv = runtime.build_run_argv(spec)
    assert argv[:5] == ["docker", "run", "--rm", "-p", "2001:2001/udp"]
    assert "--userns" not in argv  # docker has no keep-id
    assert "/h/s:/server" in argv  # no :Z relabel for docker


def test_make_runtime_selects_binary() -> None:
    assert make_runtime(AppSettings(runtime="podman")).binary == "podman"
    assert make_runtime(AppSettings(runtime="docker")).binary == "docker"
    with pytest.raises(ContainerError):
        make_runtime(AppSettings(runtime="nope"))
