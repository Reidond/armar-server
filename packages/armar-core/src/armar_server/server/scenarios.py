"""Helpers for discovering scenario ids.

Two sources: scenarios advertised by mods on their workshop page (already parsed
during ``resolve``), and the server's own ``-listScenarios`` log output.
"""

from __future__ import annotations

import re

# Matches a scenario resource id like "{1C9F8B49D438A578}Missions/ARMST_GM_Demo.conf"
_SCENARIO_ID_RE = re.compile(r"\{[0-9A-Fa-f]+\}[^\s\"']+\.conf")


def parse_list_scenarios(log_text: str) -> list[str]:
    """Extract unique scenario ``.conf`` ids from ``-listScenarios`` output."""
    seen: set[str] = set()
    found: list[str] = []
    for match in _SCENARIO_ID_RE.finditer(log_text):
        scenario_id = match.group(0)
        if scenario_id not in seen:
            seen.add(scenario_id)
            found.append(scenario_id)
    return found
