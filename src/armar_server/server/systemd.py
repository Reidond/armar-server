"""Generate systemd units for the server container.

* Podman -> a Quadlet ``.container`` file (the modern replacement for
  ``podman generate systemd``); drop it in ``~/.config/containers/systemd/``.
* Docker -> a plain ``.service`` wrapping ``docker run``.
"""

from __future__ import annotations

import shlex

from .runtime import ContainerRuntime, RunSpec


def render_quadlet(spec: RunSpec, *, description: str = "Arma Reforger dedicated server") -> str:
    lines = [
        "[Unit]",
        f"Description={description}",
        "",
        "[Container]",
        f"Image={spec.image}",
    ]
    if spec.name:
        lines.append(f"ContainerName={spec.name}")
    if spec.network == "host":
        lines.append("Network=host")
    else:
        for port in spec.ports:
            lines.append(f"PublishPort={port.host}:{port.container}/{port.protocol}")
    if spec.workdir:
        lines.append(f"WorkingDir={spec.workdir}")
    for volume in spec.volumes:
        opts = ":Z" if not volume.read_only else ":ro"
        lines.append(f"Volume={volume.host}:{volume.container}{opts}")
    for key, value in spec.env.items():
        lines.append(f"Environment={key}={value}")
    if spec.command:
        lines.append(f"Exec={shlex.join(spec.command)}")
    lines += [
        "",
        "[Service]",
        "Restart=on-failure",
        "TimeoutStartSec=900",
        "",
        "[Install]",
        "WantedBy=default.target",
        "",
    ]
    return "\n".join(lines)


def render_docker_service(
    runtime: ContainerRuntime,
    spec: RunSpec,
    *,
    description: str = "Arma Reforger dedicated server",
) -> str:
    # Force a foreground, auto-removing container so systemd supervises it directly.
    service_spec = RunSpec(
        image=spec.image,
        command=spec.command,
        name=spec.name,
        volumes=spec.volumes,
        env=spec.env,
        ports=spec.ports,
        network=spec.network,
        detach=False,
        remove=True,
        workdir=spec.workdir,
    )
    exec_start = shlex.join(runtime.build_run_argv(service_spec))
    name = spec.name or "armar-reforger"
    binary = runtime.binary
    lines = [
        "[Unit]",
        f"Description={description}",
        f"After={binary}.service",
        f"Requires={binary}.service",
        "",
        "[Service]",
        f"ExecStartPre=-/usr/bin/{binary} rm -f {name}",
        f"ExecStart={exec_start}",
        f"ExecStop=/usr/bin/{binary} stop {name}",
        "Restart=on-failure",
        "TimeoutStartSec=900",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
        "",
    ]
    return "\n".join(lines)
