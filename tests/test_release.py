"""Tests for the `release.py` script's pure next-semver logic."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from release import Version, next_version


def test_version_str_roundtrip() -> None:
    v = Version(1, 2, 3)
    assert str(v) == "1.2.3"


def test_version_bump_patch() -> None:
    v = Version(1, 2, 3)
    assert v.bump("patch") == Version(1, 2, 4)


def test_version_bump_minor_resets_patch() -> None:
    v = Version(1, 2, 3)
    assert v.bump("minor") == Version(1, 3, 0)


def test_version_bump_major_resets_minor_and_patch() -> None:
    v = Version(1, 2, 3)
    assert v.bump("major") == Version(2, 0, 0)


def test_next_version_no_tags() -> None:
    # If there are no v* tags, fall back to 0.1.0 + bump.
    v = next_version("minor")
    assert v.minor >= 1
