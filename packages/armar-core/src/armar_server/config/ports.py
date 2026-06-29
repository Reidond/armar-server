"""Pure port allocator for multi-server instances.

Allocates a disjoint {game,a2s,rcon} port triplet for a new instance,
starting at the legacy base triplet (``2001``, ``17777``, ``19999``)
plus ``n * step`` slots so existing instances aren't displaced.

The allocator is *pure*: it takes a set of already-used ports and returns
the next free triplet (or raises). It does **not** touch the filesystem
— atomicity is the registry's job (it holds a file lock while calling
this).
"""

from __future__ import annotations

from dataclasses import dataclass

# Step = 10 reserves enough headroom that a2s/rcon (+10/+20) stay
# disjoint from the next instance's game port (+30).
_STEP = 30


@dataclass(frozen=True, slots=True)
class PortTriplet:
    game: int
    a2s: int
    rcon: int


class NoFreePortsError(RuntimeError):
    """Raised when the allocator cannot find a free triplet."""


def allocate_triplet(
    used: set[int],
    *,
    base_game: int = 2001,
    base_a2s: int = 17777,
    base_rcon: int = 19999,
    max_attempts: int = 4096,
) -> PortTriplet:
    """Return the next free ``(game, a2s, rcon)`` triplet disjoint from ``used``.

    The base triplet is always treated as **reserved** (so a freshly
    installed single-server install keeps using ``2001/17777/19999``).
    """
    base = PortTriplet(base_game, base_a2s, base_rcon)
    if not _overlaps(base, used):
        return base
    n = 1
    while n < max_attempts:
        candidate = PortTriplet(base_game + n * _STEP, base_a2s + n * _STEP, base_rcon + n * _STEP)
        if not _overlaps(candidate, used):
            return candidate
        n += 1
    raise NoFreePortsError(f"no free {base_game}+n*{_STEP} triplet within {max_attempts} attempts")


def _overlaps(triplet: PortTriplet, used: set[int]) -> bool:
    return any(p in used for p in (triplet.game, triplet.a2s, triplet.rcon))


__all__ = ["NoFreePortsError", "PortTriplet", "allocate_triplet"]
