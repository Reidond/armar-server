"""Small network helpers."""

from __future__ import annotations

import socket


def detect_lan_ip() -> str:
    """Best-effort detection of this host's primary LAN IPv4 address.

    Used to populate ``publicAddress`` when running the container in bridged mode
    (in host-network mode the server auto-detects it). Returns "" on failure.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
    except OSError:
        return ""
