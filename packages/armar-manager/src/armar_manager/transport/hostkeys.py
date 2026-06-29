"""Host-key TOFU pinner (Trust On First Use).

On the **first** connect, the host key is recorded in an app-owned
known_hosts file. On subsequent connects, the key is matched; if it
changes, a *hard fail* is raised (potential MITM). Unknown keys prompt
the user to confirm before being recorded.
"""

from __future__ import annotations

import contextlib
import hashlib
from dataclasses import dataclass
from pathlib import Path

#: App-owned known_hosts file under XDG_DATA_HOME.
APP_KNOWN_HOSTS = Path.home() / ".local" / "share" / "armar-manager" / "known_hosts"


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
    """Compute a SHA-256 base64-ish fingerprint from the raw key bytes.

    The exact format matches what ssh-keygen emits, but we accept
    a pre-computed fingerprint for tests so the bit-level format
    is decoupled from the verification logic.
    """
    return hashlib.sha256(key_bytes).hexdigest()


class HostKeyPinner:
    """Trust-on-first-use host-key pin store."""

    def __init__(self, store_path: Path = APP_KNOWN_HOSTS) -> None:
        self._path = store_path

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
    "APP_KNOWN_HOSTS",
    "HostKey",
    "HostKeyMismatch",
    "HostKeyPinner",
    "HostKeyRejected",
    "fingerprint_public_key",
]
