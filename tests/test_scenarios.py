from __future__ import annotations

from armar_server.server.scenarios import parse_list_scenarios


def test_parse_list_scenarios_dedupes_and_orders() -> None:
    text = """
    SCRIPT       : {ECC61978EDCC2B5A}Missions/23_Campaign.conf
    SCRIPT       : {1C9F8B49D438A578}Missions/ARMST_GM_Demo.conf
    (again)      : {ECC61978EDCC2B5A}Missions/23_Campaign.conf
    """
    assert parse_list_scenarios(text) == [
        "{ECC61978EDCC2B5A}Missions/23_Campaign.conf",
        "{1C9F8B49D438A578}Missions/ARMST_GM_Demo.conf",
    ]


def test_parse_list_scenarios_empty() -> None:
    assert parse_list_scenarios("nothing here") == []
