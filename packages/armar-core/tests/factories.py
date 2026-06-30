"""Test helpers: build workshop ``__NEXT_DATA__`` pages and a fake client.

Keeps tests fully offline — no real network, no containers.
"""

from __future__ import annotations

import json
from typing import Any


def make_asset(
    mod_id: str,
    name: str,
    version: str,
    *,
    deps: list[tuple[str, str, str]] | None = None,
    scenarios: list[dict[str, Any]] | None = None,
    game_version: str = "1.7.0.54",
) -> dict[str, Any]:
    """Build a ``props.pageProps.asset`` dict like the real workshop site emits."""
    return {
        "id": mod_id,
        "name": name,
        "type": "addon",
        "currentVersionNumber": version,
        "gameVersion": game_version,
        "dependencies": [
            {"asset": {"id": dep_id, "name": dep_name}, "version": dep_ver, "dependencies": []}
            for (dep_id, dep_name, dep_ver) in (deps or [])
        ],
        "scenarios": [
            {
                "name": s.get("name"),
                "gameId": s["gameId"],
                "playerCount": s.get("playerCount"),
            }
            for s in (scenarios or [])
        ],
    }


def wrap_page(asset: dict[str, Any]) -> str:
    """Wrap an asset dict in a minimal page with a ``__NEXT_DATA__`` script."""
    data = {
        "props": {"pageProps": {"asset": asset, "pathId": asset["id"]}},
        "page": "/workshop/[id]",
        "query": {"id": asset["id"]},
        "buildId": "testbuild",
    }
    blob = json.dumps(data)
    return (
        "<!doctype html><html><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{blob}</script>'
        "</body></html>"
    )


def pages(*assets: dict[str, Any]) -> dict[str, str]:
    return {asset["id"]: wrap_page(asset) for asset in assets}


class FakeWorkshopClient:
    """In-memory :class:`WorkshopClient` returning pre-built pages by id."""

    def __init__(self, page_map: dict[str, str]) -> None:
        self._pages = {key.upper(): value for key, value in page_map.items()}
        self.calls: list[str] = []

    def fetch_page(self, mod_id: str) -> str:
        key = mod_id.upper()
        self.calls.append(key)
        return self._pages[key]
