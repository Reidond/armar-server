"""`SecretTokenStore` tests — pure, no Qt and no real Secret Service."""

from __future__ import annotations

import pytest
from armar_manager.secrets import InMemoryTokenBackend, SecretTokenStore


def test_inmemory_backend_roundtrip_and_delete() -> None:
    backend = InMemoryTokenBackend()
    assert backend.get("m") is None
    backend.set("m", "tok-1")
    assert backend.get("m") == "tok-1"
    backend.delete("m")
    assert backend.get("m") is None


def test_store_uses_injected_backend() -> None:
    backend = InMemoryTokenBackend()
    store = SecretTokenStore(backend=backend)
    assert store.get_token("host-a") is None
    store.set_token("host-a", "tok-a")
    assert store.get_token("host-a") == "tok-a"
    assert backend.get("host-a") == "tok-a"
    store.delete_token("host-a")
    assert store.get_token("host-a") is None


def test_store_degrades_gracefully_when_backend_raises() -> None:
    class _Broken:
        def get(self, key: str) -> str | None:
            raise RuntimeError("dbus down")

        def set(self, key: str, value: str) -> None:
            raise RuntimeError("dbus down")

        def delete(self, key: str) -> None:
            raise RuntimeError("dbus down")

    store = SecretTokenStore(backend=_Broken())
    # No exception escapes; reads just return None.
    assert store.get_token("x") is None
    store.set_token("x", "tok")  # swallowed
    store.delete_token("x")  # swallowed


def test_default_backend_falls_back_to_memory_without_secret_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import armar_manager.secrets.tokens as tokens

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("no keyring backend")

    monkeypatch.setattr(tokens, "KeyringTokenBackend", _boom)
    store = SecretTokenStore()
    # Works as an in-memory store rather than crashing.
    store.set_token("m", "tok")
    assert store.get_token("m") == "tok"
