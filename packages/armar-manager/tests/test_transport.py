"""`armar-manager` transport tests.

`HttpAgentClient` is exercised against an in-process `armar-agentd` via
the `TestClient` (so we don't need a real agentd running). Async SSH
tunnel is tested with a fake (the real asyncssh path requires an SSH
server).
"""

from __future__ import annotations

import secrets
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from armar_agentd.app import create_app
from armar_agentd.jobs import JobManager
from armar_agentd.security import AgentSettings, TokenStore
from armar_manager.transport.hostkeys import (
    HostKey,
    HostKeyMismatch,
    HostKeyPinner,
    HostKeyRejected,
)
from armar_manager.transport.http import HttpAgentClient, LocalConnection
from fastapi.testclient import TestClient


@pytest.fixture()
def agentd_workspace() -> Iterator[dict[str, Path]]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        data_dir = root / "agentd"
        token_path = data_dir / "token"
        token_path.parent.mkdir(parents=True)
        token_path.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        yield {
            "root": root,
            "data_dir": data_dir,
            "token": token_path.read_text(encoding="utf-8").strip(),
            "instances_dir": root / "instances",
        }


@pytest.fixture()
def agentd(agentd_workspace: dict[str, Path]):
    settings = AgentSettings(
        data_dir=agentd_workspace["data_dir"],
        instances_dir=agentd_workspace["instances_dir"],
    )
    token_store = TokenStore(agentd_workspace["data_dir"] / "token")
    app = create_app(agent_settings=settings, token_store=token_store, job_manager=JobManager())
    with TestClient(app) as c:
        yield {
            "client": c,
            "settings": settings,
            "token": agentd_workspace["token"],
        }


# ---- HttpAgentClient -----------------------------------------------------


def test_http_agent_client_info(agentd) -> None:

    # TestClient + a tiny WSGI shim that maps to httpx ASGI.
    from httpx import ASGITransport

    aclient = HttpAgentClient(
        base_url="http://test",
        token=agentd["token"],
        transport=ASGITransport(app=agentd["client"].app),
    )
    import asyncio

    info = asyncio.run(aclient.info())
    assert info.protocol_version >= 1
    assert info.agent_version


def test_local_connection_factory(tmp_path: Path) -> None:
    """LocalConnection constructs an httpx UDS transport."""
    conn = LocalConnection(uds_path=str(tmp_path / "fake.sock"))
    assert conn._client is not None


# ---- HostKeyPinner -------------------------------------------------------


def test_hostkey_first_use_records_key(tmp_path: Path) -> None:
    pinner = HostKeyPinner(tmp_path / "kh")
    key = HostKey(host="host-a", port=22, algorithm="ssh-ed25519", fingerprint_hex="abc")
    pinner.verify_or_record(key, confirm=lambda _: True)
    assert pinner.lookup("host-a", 22) == key


def test_hostkey_matching_key_does_not_re_prompt(tmp_path: Path) -> None:
    pinner = HostKeyPinner(tmp_path / "kh")
    key = HostKey(host="host-a", port=22, algorithm="ssh-ed25519", fingerprint_hex="abc")
    pinner.verify_or_record(key, confirm=lambda _: True)
    # Second time, no confirm needed.
    pinner.verify_or_record(key, confirm=lambda _: False)


def test_hostkey_mismatch_raises(tmp_path: Path) -> None:
    pinner = HostKeyPinner(tmp_path / "kh")
    a = HostKey(host="host-a", port=22, algorithm="ssh-ed25519", fingerprint_hex="abc")
    b = HostKey(host="host-a", port=22, algorithm="ssh-ed25519", fingerprint_hex="xyz")
    pinner.verify_or_record(a, confirm=lambda _: True)
    with pytest.raises(HostKeyMismatch):
        pinner.verify_or_record(b, confirm=lambda _: True)


def test_hostkey_rejection_raises(tmp_path: Path) -> None:
    pinner = HostKeyPinner(tmp_path / "kh")
    key = HostKey(host="host-a", port=22, algorithm="ssh-ed25519", fingerprint_hex="abc")
    with pytest.raises(HostKeyRejected):
        pinner.verify_or_record(key, confirm=lambda _: False)
    # Nothing was recorded.
    assert pinner.lookup("host-a", 22) is None


def test_default_known_hosts_path_honors_xdg_data_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from armar_manager.transport.hostkeys import default_known_hosts_path

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("HOME", raising=False)
    path = default_known_hosts_path()
    assert path == tmp_path / "xdg" / "armar-manager" / "known_hosts"


def test_default_known_hosts_path_falls_back_to_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from armar_manager.transport.hostkeys import default_known_hosts_path

    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    path = default_known_hosts_path()
    assert path == tmp_path / "home" / ".local" / "share" / "armar-manager" / "known_hosts"
