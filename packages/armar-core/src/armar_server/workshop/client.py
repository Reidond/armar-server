"""HTTP access to the Arma Workshop, behind an injectable Protocol.

``WorkshopClient`` is the seam tests mock (no real network). ``HttpWorkshopClient``
is the production implementation backed by httpx.
"""

from __future__ import annotations

import re
from types import TracebackType
from typing import Protocol, runtime_checkable

import httpx

from ..errors import WorkshopError, WorkshopFetchError

WORKSHOP_BASE_URL = "https://reforger.armaplatform.com/workshop/"

# A real browser UA; the site server-renders fine for a plain GET but we set it
# to avoid any UA-based gating.
_BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_HEX_ID_RE = re.compile(r"^[0-9A-Fa-f]{8,16}$")
_URL_ID_RE = re.compile(r"/workshop/([0-9A-Fa-f]{8,16})")


def parse_mod_id(value: str) -> str:
    """Extract an uppercase hex mod id from a workshop URL or a bare id."""
    candidate = value.strip()
    url_match = _URL_ID_RE.search(candidate)
    if url_match is not None:
        return url_match.group(1).upper()
    if _HEX_ID_RE.match(candidate):
        return candidate.upper()
    raise WorkshopError(f"Could not extract a workshop mod id from: {value!r}")


@runtime_checkable
class WorkshopClient(Protocol):
    """Fetches the raw HTML of a workshop mod page by its hex id."""

    def fetch_page(self, mod_id: str) -> str: ...


class HttpWorkshopClient:
    """Production :class:`WorkshopClient` backed by httpx."""

    def __init__(
        self,
        *,
        base_url: str = WORKSHOP_BASE_URL,
        timeout: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url
        self._client = client or httpx.Client(
            headers={"User-Agent": _BROWSER_UA},
            timeout=timeout,
            follow_redirects=True,
        )

    def fetch_page(self, mod_id: str) -> str:
        url = f"{self._base_url}{mod_id}"
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise WorkshopFetchError(
                f"Workshop returned HTTP {e.response.status_code} for mod {mod_id} ({url})."
            ) from e
        except httpx.HTTPError as e:
            raise WorkshopFetchError(f"Failed to fetch workshop page for {mod_id}: {e}") from e
        return response.text

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpWorkshopClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
