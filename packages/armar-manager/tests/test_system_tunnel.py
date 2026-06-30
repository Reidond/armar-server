"""Tests for `SystemSshTunnel` (the ssh(1) escape hatch).

This module doesn't try to spawn a real `ssh` process; the constructor
checks the binary exists, the `open` method requires a real daemon
listening on the remote side, and the rest is plumbing. We test the
shapes only.
"""

from __future__ import annotations

import shutil

import pytest
from armar_manager.transport.system_tunnel import SystemSshTunnel, TunnelError


def test_constructor_requires_ssh_binary() -> None:
    if shutil.which("ssh") is not None:
        # Skip on systems where ssh exists (which is most CI).
        pytest.skip("ssh is on PATH; cannot assert construction failure")
    with pytest.raises(TunnelError):
        SystemSshTunnel(ssh_user="u", ssh_host="h")


def test_ssh_target_format() -> None:
    t = SystemSshTunnel(ssh_user="armar", ssh_host="box.example.com", ssh_port=2222)
    assert t.ssh_target == "armar@box.example.com:2222"
