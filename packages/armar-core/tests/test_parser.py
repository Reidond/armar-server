from __future__ import annotations

import pytest

from armar_server.errors import WorkshopParseError
from armar_server.workshop.parser import parse_asset
from factories import make_asset, wrap_page


def test_parse_asset_reads_core_fields() -> None:
    asset = make_asset(
        "6922BD179EEDD0D2",
        "ARMST PLATFORM - Main mod 2.0",
        "2.0.5",
        deps=[("5D6EA74A94173EDF", "Enfusion Database Framework", "0.6.10")],
        scenarios=[
            {
                "name": "GM Demo",
                "gameId": "{1C9F8B49D438A578}Missions/ARMST_GM_Demo.conf",
                "playerCount": 64,
            }
        ],
    )
    parsed = parse_asset(wrap_page(asset))
    assert parsed.id == "6922BD179EEDD0D2"
    assert parsed.name.startswith("ARMST")
    assert parsed.currentVersionNumber == "2.0.5"
    # dependency id is nested one level deeper, at dependencies[i].asset.id
    assert parsed.dependencies[0].asset.id == "5D6EA74A94173EDF"
    assert parsed.scenarios[0].gameId.endswith("ARMST_GM_Demo.conf")
    assert parsed.scenarios[0].playerCount == 64


def test_parse_asset_missing_script() -> None:
    with pytest.raises(WorkshopParseError):
        parse_asset("<html><body>no script here</body></html>")


def test_parse_asset_no_asset() -> None:
    html = '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>'
    with pytest.raises(WorkshopParseError):
        parse_asset(html)
