"""Resolve a set of top-level mods into the full, pinned dependency closure.

For each unique mod we fetch its page once (cached), recurse into its
dependencies, and pin the mod's *current latest* version — matching what the
in-game Mod Manager produces when you copy the JSON. Output is ordered
dependencies-before-dependents, deduplicated, with a cycle guard.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace

from ..logging import get_logger
from .client import WorkshopClient
from .models import Asset, Scenario
from .parser import parse_asset


@dataclass(frozen=True)
class ResolvedMod:
    mod_id: str
    name: str
    version: str | None
    direct: bool


@dataclass
class ResolveResult:
    mods: list[ResolvedMod]
    scenarios: list[tuple[str, Scenario]]  # (mod_id, scenario) from direct mods
    game_version: str | None


def _version_key(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    parts: list[int] = []
    for chunk in value.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


class DependencyResolver:
    def __init__(self, client: WorkshopClient, *, logger: logging.Logger | None = None) -> None:
        self._client = client
        self._cache: dict[str, Asset] = {}
        self._log = logger or get_logger(__name__)

    def _asset(self, mod_id: str) -> Asset:
        key = mod_id.upper()
        cached = self._cache.get(key)
        if cached is None:
            cached = parse_asset(self._client.fetch_page(key))
            self._cache[key] = cached
        return cached

    def resolve(self, top_level: Sequence[str]) -> ResolveResult:
        resolved: dict[str, ResolvedMod] = {}
        order: list[str] = []
        in_progress: set[str] = set()

        def visit(mod_id: str, *, is_direct: bool) -> None:
            key = mod_id.upper()
            existing = resolved.get(key)
            if existing is not None:
                if is_direct and not existing.direct:
                    resolved[key] = replace(existing, direct=True)
                return
            if key in in_progress:
                self._log.warning("Dependency cycle detected at %s; skipping back-edge.", key)
                return
            in_progress.add(key)
            asset = self._asset(key)
            for dep in asset.dependencies:
                visit(dep.asset.id, is_direct=False)
            resolved[key] = ResolvedMod(
                mod_id=key,
                name=asset.name,
                version=asset.currentVersionNumber,
                direct=is_direct,
            )
            order.append(key)
            in_progress.discard(key)

        for mid in top_level:
            visit(mid, is_direct=True)

        mods = [resolved[k] for k in order]
        scenarios: list[tuple[str, Scenario]] = []
        for mod in mods:
            if not mod.direct:
                continue
            asset = self._cache.get(mod.mod_id)
            if asset is not None:
                scenarios.extend((mod.mod_id, scenario) for scenario in asset.scenarios)

        game_version: str | None = None
        for asset in self._cache.values():
            if asset.gameVersion and _version_key(asset.gameVersion) > _version_key(game_version):
                game_version = asset.gameVersion

        return ResolveResult(mods=mods, scenarios=scenarios, game_version=game_version)
