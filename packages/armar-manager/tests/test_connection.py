"""`dial_remote` / `rotate_remote_token` tests — Qt-free, no sshd, no D-Bus.

A `FakeTunnel` stands in for the SSH local-forward (records exec calls and
whether it was closed); a `FakeClient` stands in for the HTTP agent client.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from armar_manager.secrets import InMemoryTokenBackend, Machine, SecretTokenStore
from armar_manager.transport.connection import dial_remote, rotate_remote_token
from armar_manager.transport.tunnel import TunnelError

from armar_server.contracts import PROTOCOL_VERSION, AgentInfo


class FakeTunnel:
    def __init__(self, *, exec_result: tuple[int, str, str], local_port: int = 51515) -> None:
        self._exec_result = exec_result
        self._local_port = local_port
        self.exec_calls: list[str] = []
        self.opened = False
        self.closed = False

    async def open(self) -> SimpleNamespace:
        self.opened = True
        return SimpleNamespace(local_port=self._local_port)

    async def exec(self, command: str, *, timeout: float = 30.0) -> tuple[int, str, str]:
        self.exec_calls.append(command)
        return self._exec_result

    async def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(self, *, base_url: str, token: str | None, protocol_version: int) -> None:
        self.base_url = base_url
        self.token = token
        self._protocol_version = protocol_version
        self.closed = False

    async def info(self) -> AgentInfo:
        return AgentInfo(
            agent_version="0.0.0-test",
            protocol_version=self._protocol_version,
            hostname="fake",
            started_at=datetime.now(UTC),
        )

    async def close(self) -> None:
        self.closed = True


def _machine() -> Machine:
    return Machine(name="host-a", ssh_user="ops", ssh_host="example.com")


def _factories(tunnel: FakeTunnel, *, protocol_version: int = PROTOCOL_VERSION):
    captured: dict[str, FakeClient] = {}

    def tunnel_factory(**_kwargs: object) -> FakeTunnel:
        return tunnel

    def client_factory(*, base_url: str, token: str | None) -> FakeClient:
        client = FakeClient(base_url=base_url, token=token, protocol_version=protocol_version)
        captured["client"] = client
        return client

    return tunnel_factory, client_factory, captured


def test_dial_obtains_persists_and_uses_token_when_store_empty() -> None:
    tunnel = FakeTunnel(exec_result=(0, "secret-token\n", ""))
    store = SecretTokenStore(backend=InMemoryTokenBackend())
    tf, cf, captured = _factories(tunnel)

    result = asyncio.run(
        dial_remote(_machine(), token_store=store, tunnel_factory=tf, client_factory=cf)
    )

    assert tunnel.exec_calls == ["armar-agentd token print"]
    assert store.get_token("host-a") == "secret-token"
    assert captured["client"].token == "secret-token"
    assert captured["client"].base_url == "http://127.0.0.1:51515"
    assert result.client is captured["client"]
    assert not tunnel.closed


def test_dial_reuses_stored_token_without_exec() -> None:
    tunnel = FakeTunnel(exec_result=(0, "should-not-be-read\n", ""))
    store = SecretTokenStore(backend=InMemoryTokenBackend())
    store.set_token("host-a", "stored-token")
    tf, cf, captured = _factories(tunnel)

    asyncio.run(dial_remote(_machine(), token_store=store, tunnel_factory=tf, client_factory=cf))

    assert tunnel.exec_calls == []
    assert captured["client"].token == "stored-token"


def test_dial_blank_token_print_raises_and_persists_nothing() -> None:
    tunnel = FakeTunnel(exec_result=(0, "   \n", ""))
    store = SecretTokenStore(backend=InMemoryTokenBackend())
    tf, cf, _ = _factories(tunnel)

    with pytest.raises(TunnelError):
        asyncio.run(
            dial_remote(_machine(), token_store=store, tunnel_factory=tf, client_factory=cf)
        )
    assert store.get_token("host-a") is None
    assert tunnel.closed


def test_dial_failed_token_print_exit_code_raises() -> None:
    tunnel = FakeTunnel(exec_result=(127, "", "command not found"))
    store = SecretTokenStore(backend=InMemoryTokenBackend())
    tf, cf, _ = _factories(tunnel)

    with pytest.raises(TunnelError):
        asyncio.run(
            dial_remote(_machine(), token_store=store, tunnel_factory=tf, client_factory=cf)
        )
    assert store.get_token("host-a") is None
    assert tunnel.closed


def test_dial_protocol_mismatch_raises_and_closes() -> None:
    tunnel = FakeTunnel(exec_result=(0, "tok\n", ""))
    store = SecretTokenStore(backend=InMemoryTokenBackend())
    tf, cf, captured = _factories(tunnel, protocol_version=PROTOCOL_VERSION + 999)

    with pytest.raises(TunnelError):
        asyncio.run(
            dial_remote(_machine(), token_store=store, tunnel_factory=tf, client_factory=cf)
        )
    assert tunnel.closed
    assert captured["client"].closed


def test_rotate_persists_and_returns_new_token() -> None:
    tunnel = FakeTunnel(exec_result=(0, "rotated-token\n", ""))
    store = SecretTokenStore(backend=InMemoryTokenBackend())
    store.set_token("host-a", "old-token")

    new = asyncio.run(rotate_remote_token(_machine(), token_store=store, tunnel=tunnel))

    assert new == "rotated-token"
    assert tunnel.exec_calls == ["armar-agentd token rotate"]
    assert store.get_token("host-a") == "rotated-token"
