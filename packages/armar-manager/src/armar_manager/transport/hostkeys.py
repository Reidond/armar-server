"""Host-key TOFU pinner (Trust On First Use).

On the **first** connect, the host key is recorded in an app-owned
known_hosts file. On subsequent connects, the key is matched; if it
changes, a *hard fail* is raised (potential MITM). Unknown keys prompt
the user to confirm before being recorded.

Path resolution:

- Honor ``$XDG_DATA_HOME`` first, then fall back to ``~/.local/share``
  (so the Flatpak sandbox can override the location).
- Inside a Flatpak, ``$HOME`` maps to ``~/.var/app/<id>/`` and the
  per-app data dir is therefore ``~/.var/app/<id>/data/armar-manager`` —
  no extra ``--filesystem`` permission is needed.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

#: App-owned known_hosts file. Resolved at instance time via
#: :py:func:`default_known_hosts_path` so ``$XDG_DATA_HOME`` is honored.
APP_KNOWN_HOSTS_NAME = "armar-manager/known_hosts"


class HostKeyMismatch(RuntimeError):
    """Raised when the host key has changed since the first connect."""


class HostKeyRejected(RuntimeError):
    """Raised when the user declines to trust a new host key."""


@dataclass(frozen=True)
class HostKey:
    """A single host key entry: the key fingerprint + the host:port it belongs to."""

    host: str
    port: int
    algorithm: str  # "ssh-ed25519", "ssh-rsa", "ecdsa-sha2-nistp256", ...
    fingerprint_hex: str

    def line(self) -> str:
        return f"{self.host}:{self.port} {self.algorithm} {self.fingerprint_hex}"


def _parse_line(line: str) -> HostKey | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split()
    if len(parts) != 3:
        return None
    marker, algo, fp = parts
    if ":" not in marker:
        return None
    host, _, port_s = marker.partition(":")
    try:
        port = int(port_s)
    except ValueError:
        return None
    return HostKey(host=host, port=port, algorithm=algo, fingerprint_hex=fp)


def fingerprint_public_key(key_bytes: bytes, algorithm: str) -> str:
    """Compute a SHA-256 base64-ish fingerprint from the raw key bytes."""
    _ = algorithm
    return hashlib.sha256(key_bytes).hexdigest()


def default_known_hosts_path() -> Path:
    """Return the per-user known_hosts path, honoring ``$XDG_DATA_HOME``.

    Resolves to ``$XDG_DATA_HOME/armar-manager/known_hosts`` if set,
    otherwise ``~/.local/share/armar-manager/known_hosts``. Inside a
    Flatpak, ``$HOME`` is ``~/.var/app/<id>/`` and the data dir is
    therefore under the per-app ``data/`` — no ``--filesystem`` hole
    is needed.
    """
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / APP_KNOWN_HOSTS_NAME


class HostKeyPinner:
    """Trust-on-first-use host-key pin store."""

    def __init__(self, store_path: Path | None = None) -> None:
        self._path = store_path or default_known_hosts_path()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[HostKey]:
        if not self._path.exists():
            return []
        out: list[HostKey] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            entry = _parse_line(line)
            if entry is not None:
                out.append(entry)
        return out

    def lookup(self, host: str, port: int) -> HostKey | None:
        for entry in self.load():
            if entry.host == host and entry.port == port:
                return entry
        return None

    def verify_or_record(
        self,
        key: HostKey,
        *,
        confirm: callable,  # type: ignore[type-arg]
    ) -> None:
        """Verify the presented key against the pinned entry.

        - Unknown: call ``confirm(key)``; if it returns truthy, record
          and return. If it returns falsy, raise ``HostKeyRejected``.
        - Known + matching: return.
        - Known + mismatch: raise ``HostKeyMismatch``.
        """
        existing = self.lookup(key.host, key.port)
        if existing is None:
            if not confirm(key):
                raise HostKeyRejected(f"user declined to trust {key.host}:{key.port}")
            self._record(key)
            return
        if existing.algorithm != key.algorithm or existing.fingerprint_hex != key.fingerprint_hex:
            raise HostKeyMismatch(
                f"host key for {key.host}:{key.port} has changed! "
                f"pinned={existing.algorithm}:{existing.fingerprint_hex} "
                f"presented={key.algorithm}:{key.fingerprint_hex}"
            )

    def _record(self, key: HostKey) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fp:
            fp.write(key.line() + "\n")
        with contextlib.suppress(OSError):  # not all platforms support chmod
            self._path.chmod(0o600)


__all__ = [
    "APP_KNOWN_HOSTS_NAME",
    "HostKey",
    "HostKeyMismatch",
    "HostKeyPinner",
    "HostKeyRejected",
    "default_known_hosts_path",
    "fingerprint_public_key",
]
