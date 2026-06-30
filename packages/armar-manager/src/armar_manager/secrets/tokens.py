"""Agent-token storage backed by the freedesktop Secret Service.

The remote ``armar-agentd`` requires a bearer token on every
authenticated route. The desktop obtains it once over SSH-exec
(``armar-agentd token print`` — see ``transport/connection.py``) and
persists it here so later connects don't need another round-trip.

Per the design the token is **never** sent over HTTP (only as the
``Authorization`` header) and **never** written to ``machines.toml``.
Persistence uses ``keyring`` (Secret Service on Linux). If no Secret
Service is reachable (headless dev box, a sandbox without the
``org.freedesktop.secrets`` portal), the store degrades to a
process-local in-memory backend — connects still work, the token is
just re-fetched via SSH-exec on the next launch.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

SERVICE_NAME = "armar-manager"


@runtime_checkable
class TokenBackend(Protocol):
    """Minimal secret get/set/delete keyed by a string."""

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> None: ...


class InMemoryTokenBackend:
    """Process-local backend (tests + graceful fallback)."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def set(self, key: str, value: str) -> None:
        self._values[key] = value

    def delete(self, key: str) -> None:
        self._values.pop(key, None)


class KeyringTokenBackend:
    """``keyring``-backed backend (Secret Service on Linux).

    Lazily imports ``keyring`` and probes for a usable backend at
    construction so callers can fall back when none exists.
    """

    def __init__(self, service: str = SERVICE_NAME) -> None:
        import keyring
        from keyring.backends import fail

        active = keyring.get_keyring()
        if isinstance(active, fail.Keyring):
            raise RuntimeError("no usable keyring backend (Secret Service unavailable)")
        self._keyring = keyring
        self._service = service

    def get(self, key: str) -> str | None:
        return self._keyring.get_password(self._service, key)

    def set(self, key: str, value: str) -> None:
        self._keyring.set_password(self._service, key, value)

    def delete(self, key: str) -> None:
        import contextlib

        import keyring.errors

        with contextlib.suppress(keyring.errors.PasswordDeleteError):
            self._keyring.delete_password(self._service, key)


class SecretTokenStore:
    """Per-machine agent-token store.

    Defaults to the Secret Service via :class:`KeyringTokenBackend`,
    falling back to :class:`InMemoryTokenBackend` when no Secret Service
    is reachable. Every backend call is guarded so a Secret Service
    hiccup degrades gracefully (a failed read returns ``None`` → the
    caller re-fetches the token over SSH) instead of crashing the UI.
    """

    def __init__(self, backend: TokenBackend | None = None) -> None:
        self._backend = backend if backend is not None else self._default_backend()

    @staticmethod
    def _default_backend() -> TokenBackend:
        try:
            return KeyringTokenBackend()
        except Exception as exc:  # ImportError / no backend / D-Bus errors
            logger.warning("Secret Service unavailable (%s); agent tokens kept in memory only", exc)
            return InMemoryTokenBackend()

    def get_token(self, machine_name: str) -> str | None:
        try:
            return self._backend.get(machine_name)
        except Exception as exc:
            logger.warning("token read for %r failed: %s", machine_name, exc)
            return None

    def set_token(self, machine_name: str, token: str) -> None:
        try:
            self._backend.set(machine_name, token)
        except Exception as exc:
            logger.warning("token write for %r failed: %s", machine_name, exc)

    def delete_token(self, machine_name: str) -> None:
        try:
            self._backend.delete(machine_name)
        except Exception as exc:
            logger.warning("token delete for %r failed: %s", machine_name, exc)


__all__ = [
    "SERVICE_NAME",
    "InMemoryTokenBackend",
    "KeyringTokenBackend",
    "SecretTokenStore",
    "TokenBackend",
]
