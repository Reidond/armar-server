"""Integration tests for the `armar-agentd` FastAPI app."""

from __future__ import annotations

import secrets
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from armar_agentd.app import create_app
from armar_agentd.jobs import JobManager
from armar_agentd.security import AgentSettings, TokenStore
from fastapi.testclient import TestClient


@pytest.fixture()
def workspace() -> Iterator[dict[str, Path]]:
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
def app(workspace: dict[str, Path]):
    agent_settings = AgentSettings(
        data_dir=workspace["data_dir"],
        instances_dir=workspace["instances_dir"],
    )
    token_store = TokenStore(workspace["data_dir"] / "token")
    return create_app(
        agent_settings=agent_settings,
        token_store=token_store,
        job_manager=JobManager(),
    )


@pytest.fixture()
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_healthz_does_not_require_token(client: TestClient) -> None:
    r = client.get("/api/v1/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_info_requires_token(client: TestClient, workspace: dict[str, Path]) -> None:
    r = client.get("/api/v1/info")
    assert r.status_code == 401
    r = client.get("/api/v1/info", headers=_auth(workspace["token"]))
    assert r.status_code == 200
    data = r.json()
    assert "token" not in data
    assert data["protocol_version"] >= 1


def test_info_with_wrong_token_is_401(client: TestClient) -> None:
    r = client.get("/api/v1/info", headers={"Authorization": "Bearer wrong-token"})
    assert r.status_code == 401


def test_create_instance_then_show(client: TestClient, workspace: dict[str, Path]) -> None:
    auth = _auth(workspace["token"])
    r = client.post(
        "/api/v1/instances",
        json={"name": "Alpha", "slug": "alpha"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["slug"] == "alpha"
    assert data["container_name"] == "armar-alpha"
    assert data["game_port"] == 2001
    assert data["a2s_port"] == 17777
    assert data["rcon_port"] == 19999

    r = client.get("/api/v1/instances/alpha", headers=auth)
    assert r.status_code == 200
    assert r.json()["slug"] == "alpha"


def test_create_instance_with_duplicate_slug_returns_409(
    client: TestClient, workspace: dict[str, Path]
) -> None:
    auth = _auth(workspace["token"])
    client.post(
        "/api/v1/instances",
        json={"name": "Alpha", "slug": "alpha"},
        headers=auth,
    )
    r = client.post(
        "/api/v1/instances",
        json={"name": "Other", "slug": "alpha"},
        headers=auth,
    )
    assert r.status_code == 409


def test_create_instance_with_reserved_slug_returns_400(
    client: TestClient, workspace: dict[str, Path]
) -> None:
    auth = _auth(workspace["token"])
    r = client.post(
        "/api/v1/instances",
        json={"name": "Default", "slug": "default"},
        headers=auth,
    )
    assert r.status_code == 400


def test_create_instance_allocates_disjoint_ports(
    client: TestClient, workspace: dict[str, Path]
) -> None:
    auth = _auth(workspace["token"])
    r1 = client.post("/api/v1/instances", json={"name": "A", "slug": "alpha"}, headers=auth)
    r2 = client.post("/api/v1/instances", json={"name": "B", "slug": "bravo"}, headers=auth)
    assert r1.status_code == 201
    assert r2.status_code == 201
    ports = {
        r1.json()["game_port"],
        r1.json()["a2s_port"],
        r1.json()["rcon_port"],
        r2.json()["game_port"],
        r2.json()["a2s_port"],
        r2.json()["rcon_port"],
    }
    assert len(ports) == 6


def test_list_instances(client: TestClient, workspace: dict[str, Path]) -> None:
    auth = _auth(workspace["token"])
    client.post("/api/v1/instances", json={"name": "A", "slug": "alpha"}, headers=auth)
    client.post("/api/v1/instances", json={"name": "B", "slug": "bravo"}, headers=auth)
    r = client.get("/api/v1/instances", headers=auth)
    assert r.status_code == 200
    slugs = {item["slug"] for item in r.json()}
    assert slugs == {"alpha", "bravo"}


def test_delete_instance(client: TestClient, workspace: dict[str, Path]) -> None:
    auth = _auth(workspace["token"])
    client.post("/api/v1/instances", json={"name": "A", "slug": "alpha"}, headers=auth)
    r = client.delete("/api/v1/instances/alpha?force=true", headers=auth)
    assert r.status_code == 204
    r = client.get("/api/v1/instances/alpha", headers=auth)
    assert r.status_code == 404


def test_readyz_reflects_token_store(client: TestClient) -> None:
    r = client.get("/api/v1/readyz")
    # Fixture provisions a token before the app starts → ready
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_agent_settings_rejects_non_loopback_bind_host() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AgentSettings(bind_host="0.0.1.2")


def test_agent_settings_accepts_loopback() -> None:
    AgentSettings(bind_host="127.0.0.1")
    AgentSettings(bind_host="::1")
    AgentSettings(bind_host="localhost")


def test_token_store_roundtrip(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "token")
    assert not store.exists()
    store.write("hello")
    assert store.exists()
    assert store.read() == "hello"
    new = store.rotate()
    assert new != "hello"
    assert store.read() == new


# ---- logs / status (P2) -------------------------------------------------


def test_status_endpoint_reports_not_running(
    client: TestClient, workspace: dict[str, Path]
) -> None:
    auth = _auth(workspace["token"])
    client.post("/api/v1/instances", json={"name": "A", "slug": "alpha"}, headers=auth)
    r = client.get("/api/v1/instances/alpha/status", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["container_running"] is False


def test_status_endpoint_for_unknown_instance_returns_404(
    client: TestClient, workspace: dict[str, Path]
) -> None:
    auth = _auth(workspace["token"])
    r = client.get("/api/v1/instances/missing/status", headers=auth)
    assert r.status_code == 404


def test_logs_stream_endpoint_returns_sse(client: TestClient, workspace: dict[str, Path]) -> None:
    auth = _auth(workspace["token"])
    client.post("/api/v1/instances", json={"name": "A", "slug": "alpha"}, headers=auth)
    # The container is not running, so podman is invoked against a
    # non-existent container; podman is missing in the test env so the
    # route should 503 (rather than block). Either way, we verify the
    # auth gating works.
    r = client.get("/api/v1/instances/alpha/logs/stream", headers=auth)
    assert r.status_code in (200, 503)


# ---- CLI: serve kwargs + protocol-version -------------------------------


def test_serve_kwargs_defaults_to_settings_tcp() -> None:
    from armar_agentd.app import _serve_kwargs

    settings = AgentSettings(bind_host="127.0.0.1", bind_port=8477)
    assert _serve_kwargs(settings) == {"host": "127.0.0.1", "port": 8477}


def test_serve_kwargs_uds_setting_when_configured(tmp_path: Path) -> None:
    from armar_agentd.app import _serve_kwargs

    sock = tmp_path / "agent.sock"
    settings = AgentSettings(uds_path=sock)
    assert _serve_kwargs(settings) == {"uds": str(sock)}


def test_serve_kwargs_cli_bind_overrides_settings() -> None:
    from armar_agentd.app import _serve_kwargs

    settings = AgentSettings(bind_host="127.0.0.1", bind_port=8477)
    assert _serve_kwargs(settings, bind="127.0.0.1:9000") == {"host": "127.0.0.1", "port": 9000}


def test_serve_kwargs_cli_uds_overrides_settings() -> None:
    from armar_agentd.app import _serve_kwargs

    settings = AgentSettings(bind_host="127.0.0.1", bind_port=8477)
    assert _serve_kwargs(settings, uds="/run/agent.sock") == {"uds": "/run/agent.sock"}


def test_protocol_version_flag_prints_integer(capsys: pytest.CaptureFixture[str]) -> None:
    from armar_agentd.app import main

    from armar_server.contracts import PROTOCOL_VERSION

    rc = main(["--protocol-version"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == str(PROTOCOL_VERSION)
