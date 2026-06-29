"""`scripts/release.py` — pure next-semver + precondition functions.

Run via `uv run scripts/release.py [bump]`.

Bumps are: major | minor | patch (default: patch).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class ReleaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump(self, kind: str) -> Version:
        if kind == "major":
            return Version(self.major + 1, 0, 0)
        if kind == "minor":
            return Version(self.major, self.minor + 1, 0)
        if kind == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ReleaseError(f"unknown bump kind: {kind!r}")


_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def latest_tag() -> Version | None:
    """Return the highest ``vX.Y.Z`` tag, or None if no tags exist."""
    proc = subprocess.run(
        ["/usr/bin/git", "tag", "--list", "v*", "--sort=-v:refname"],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in proc.stdout.splitlines():
        match = _TAG_RE.match(line.strip())
        if match:
            return Version(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def next_version(bump: str = "patch") -> Version:
    base = latest_tag() or Version(0, 1, 0)
    return base.bump(bump)


def check_clean_tree() -> None:
    proc = subprocess.run(
        ["/usr/bin/git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    if proc.stdout.strip():
        raise ReleaseError("working tree is not clean; commit or stash first")


def check_on_main() -> None:
    proc = subprocess.run(
        ["/usr/bin/git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    branch = proc.stdout.strip()
    if branch != "main":
        raise ReleaseError(f"must be on main (currently on {branch!r})")


def create_tag(
    version: Version, *, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run
) -> None:
    tag = f"v{version}"
    runner(["git", "tag", "-a", tag, "-m", f"Release {tag}"], check=True)
    runner(["git", "push", "origin", tag], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release")
    parser.add_argument("bump", nargs="?", default="patch", choices=["major", "minor", "patch"])
    parser.add_argument("--dry-run", action="store_true", help="Print the next version and exit")
    args = parser.parse_args(argv)

    check_clean_tree()
    check_on_main()
    version = next_version(args.bump)
    if args.dry_run:
        print(version)
        return 0
    create_tag(version)
    print(f"created v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


__all__ = [
    "ReleaseError",
    "Version",
    "check_clean_tree",
    "check_on_main",
    "create_tag",
    "latest_tag",
    "next_version",
]


# Sentinel so the import isn't dead.
_ = Path
