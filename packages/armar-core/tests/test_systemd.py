from __future__ import annotations

from armar_server.server.runtime import DockerRuntime, PortMapping, RunSpec, VolumeMount
from armar_server.server.systemd import render_docker_service, render_quadlet


def test_render_quadlet() -> None:
    spec = RunSpec(
        image="armar-reforger:latest",
        command=["/server/ArmaReforgerServer", "-config", "/config/c.json"],
        name="armar",
        network="host",
        volumes=[VolumeMount("/h/s", "/server")],
        workdir="/server",
    )
    unit = render_quadlet(spec)
    assert "[Container]" in unit
    assert "Image=armar-reforger:latest" in unit
    assert "Network=host" in unit
    assert "Volume=/h/s:/server:Z" in unit
    assert "Exec=/server/ArmaReforgerServer -config /config/c.json" in unit
    assert "Restart=on-failure" in unit


def test_render_docker_service() -> None:
    runtime = DockerRuntime()
    spec = RunSpec(
        image="img",
        command=["/server/ArmaReforgerServer"],
        name="armar",
        ports=[PortMapping(2001, 2001, "udp")],
        volumes=[VolumeMount("/h/s", "/server")],
    )
    unit = render_docker_service(runtime, spec)
    assert "ExecStart=" in unit
    assert "docker run" in unit
    assert "--rm" in unit
    assert "ExecStop=/usr/bin/docker stop armar" in unit
