from __future__ import annotations

from armar_server.workshop.resolver import DependencyResolver
from factories import FakeWorkshopClient, make_asset, pages


def test_resolve_diamond_dedup_and_order() -> None:
    # A -> B,C ; B -> D ; C -> D  (D is shared; pinned to D's own latest version)
    a = make_asset(
        "A",
        "Mod A",
        "1.0",
        deps=[("B", "Mod B", "1.0"), ("C", "Mod C", "1.0")],
        scenarios=[{"name": "S", "gameId": "{X}Missions/s.conf"}],
    )
    b = make_asset("B", "Mod B", "1.0", deps=[("D", "Mod D", "1.0")])
    c = make_asset("C", "Mod C", "1.0", deps=[("D", "Mod D", "1.0")])
    d = make_asset("D", "Mod D", "2.3")
    client = FakeWorkshopClient(pages(a, b, c, d))

    result = DependencyResolver(client).resolve(["A"])
    ids = [m.mod_id for m in result.mods]

    assert set(ids) == {"A", "B", "C", "D"}
    assert ids.count("D") == 1  # deduplicated
    assert ids.index("D") < ids.index("B")  # deps before dependents
    assert ids.index("B") < ids.index("A")

    by_id = {m.mod_id: m for m in result.mods}
    assert by_id["A"].direct is True
    assert by_id["B"].direct is False
    # pinned from each mod's OWN page (latest), not the parent's requested version
    assert by_id["D"].version == "2.3"

    # one fetch per unique mod (cache works)
    assert sorted(set(client.calls)) == ["A", "B", "C", "D"]
    assert len(client.calls) == 4

    # scenarios collected from direct mods only
    assert result.scenarios[0][0] == "A"
    assert result.scenarios[0][1].gameId.endswith("s.conf")
    assert result.game_version is not None


def test_resolve_cycle_guard() -> None:
    e = make_asset("E", "E", "1.0", deps=[("F", "F", "1.0")])
    f = make_asset("F", "F", "1.0", deps=[("E", "E", "1.0")])
    client = FakeWorkshopClient(pages(e, f))

    result = DependencyResolver(client).resolve(["E"])
    assert {m.mod_id for m in result.mods} == {"E", "F"}
