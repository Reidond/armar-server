"""Parse a workshop page's HTML into an :class:`Asset`.

Strategy (validated against a live page): a single GET yields HTML containing one
``<script id="__NEXT_DATA__" type="application/json">{...}</script>``. Parse that
JSON and read ``props.pageProps.asset`` — no headless browser, no private API.
Also accepts an already-decoded ``__NEXT_DATA__`` dict (used by tests/fixtures).
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..errors import WorkshopParseError
from .models import Asset

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def extract_next_data(html: str) -> dict[str, Any]:
    match = _NEXT_DATA_RE.search(html)
    if match is None:
        raise WorkshopParseError("No __NEXT_DATA__ script tag found in workshop page HTML.")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        raise WorkshopParseError(f"Could not decode __NEXT_DATA__ JSON: {e}") from e
    if not isinstance(data, dict):
        raise WorkshopParseError("__NEXT_DATA__ did not decode to an object.")
    return data


def asset_from_next_data(next_data: dict[str, Any]) -> Asset:
    try:
        asset_data = next_data["props"]["pageProps"]["asset"]
    except (KeyError, TypeError) as e:
        raise WorkshopParseError(
            "Unexpected page structure: props.pageProps.asset is missing."
        ) from e
    if not asset_data:
        raise WorkshopParseError(
            "Workshop page contained no asset data (mod not found, unlisted, or removed?)."
        )
    return Asset.model_validate(asset_data)


def parse_asset(html: str) -> Asset:
    return asset_from_next_data(extract_next_data(html))
