"""`armar-agentd install|uninstall|token|doctor` subcommands.

Renders a hardened ``systemd --user`` unit, ``enable-linger``, generates
a token at ``<data_dir>/token`` (mode 0600), and prints a one-line
``AgentInfo`` JSON between explicit sentinels for the install script.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from armar_server import __version__ as armar_core_version
from armar_server.contracts import PROTOCOL_VERSION

from ..security import AgentSettings, TokenStore

UNIT_NAME = "armar-agentd.service"


def install() -> int:
    settings = AgentSettings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    token_store = TokenStore(settings.data_dir / "token")
    if not token_store.exists():
        token_store.write(TokenStore.generate())
        with contextlib.suppress(OSError):
            token_store.path.chmod(0o600)

    _enable_linger()
    _write_unit(settings)
    _daemon_reload()
    _systemctl("--user", "enable", "--now", UNIT_NAME)
    info = _emit_info(settings)
    print(f"__ARMAR_AGENTD_INSTALLED__ {json.dumps(info)} __END__", file=sys.stderr)
    return 0


def uninstall() -> int:
    settings = AgentSettings()
    _systemctl("--user", "disable", "--now", UNIT_NAME, check=False)
    unit = _unit_path()
    if unit.exists():
        unit.unlink()
    _daemon_reload()
    if settings.data_dir.exists() and not any(settings.data_dir.iterdir()):
        settings.data_dir.rmdir()
    return 0


def doctor() -> int:
    settings = AgentSettings()
    checks: list[tuple[str, bool, str]] = []
    checks.append(("uv", bool(shutil.which("uv")), "uv on PATH"))
    checks.append(
        ("podman", bool(shutil.which(settings.runtime_binary())), "container runtime on PATH")
    )
    token_store = TokenStore(settings.data_dir / "token")
    checks.append(("token", token_store.exists(), f"{token_store.path}"))
    checks.append(("linger", _has_linger(), "loginctl show-user"))
    for name, ok, detail in checks:
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
    return 0 if all(ok for _, ok, _ in checks) else 1


def token_print() -> int:
    settings = AgentSettings()
    token = TokenStore(settings.data_dir / "token")
    if not token.exists():
        print("token not provisioned; run `armar-agentd install`", file=sys.stderr)
        return 1
    print(token.read())
    return 0


def token_rotate() -> int:
    settings = AgentSettings()
    new = TokenStore(settings.data_dir / "token").rotate()
    print(new)
    return 0


# --- helpers ---------------------------------------------------------------


def _emit_info(settings: AgentSettings) -> dict[str, object]:
    return {
        "agent_version": armar_core_version,
        "protocol_version": PROTOCOL_VERSION,
        "hostname": _hostname(),
        "data_dir": str(settings.data_dir),
        "bind_host": settings.bind_host,
        "bind_port": settings.bind_port,
        "uds_path": str(settings.uds_path) if settings.uds_path else None,
        "started_at": datetime.now(UTC).isoformat(),
    }


def _hostname() -> str:
    import socket

    try:
        return socket.gethostname()
    except OSError:
        return "unknown"


def _write_unit(settings: AgentSettings) -> None:
    target = _unit_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_render_unit(settings), encoding="utf-8")


def _render_unit(settings: AgentSettings) -> str:
    # Hardened unit: deny privilege escalation, restrict address families,
    # give rootless podman the userns + runtime dir it needs.
    exec_start = "/usr/bin/env"
    if settings.uds_path:
        exec_start += f" uv run --no-sync armar-agentd serve --uds {settings.uds_path}"
    else:
        exec_start += (
            f" uv run --no-sync armar-agentd serve --bind {settings.bind_host}:{settings.bind_port}"
        )
    return f"""[Unit]
Description=armar-agentd (Reforger fleet agent)
After=network-online.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
MemoryMax=512M
TasksMax=128
# Rootless podman needs these.
IPCNamespace=private

[Install]
WantedBy=default.target
"""


def _unit_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / UNIT_NAME


def _daemon_reload() -> None:
    _systemctl("--user", "daemon-reload")


def _enable_linger() -> None:
    if os.geteuid() == 0:
        return  # running as root in a container; nothing to do
    _systemctl("loginctl", "enable-linger", os.environ.get("USER", ""), check=False)


def _has_linger() -> bool:
    if os.geteuid() == 0:
        return True
    user = os.environ.get("USER", "")
    if not user:
        return False
    result = subprocess.run(  # noqa: S603 — argv is fixed (loginctl + subcommand)
        ["loginctl", "show-user", user, "--property", "Linger"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return "yes" in result.stdout.lower()


def _systemctl(*args: str, check: bool = True) -> None:
    result = subprocess.run(  # noqa: S603 — argv is fixed (systemctl + subcommand)
        ["/usr/bin/systemctl", *args], capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        print(
            f"systemctl {' '.join(args)} -> {result.returncode}\n{result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(result.returncode)


# Sentinel: ensure PROTOCOL_VERSION is referenced so ruff does not strip it.
_ = PROTOCOL_VERSION
