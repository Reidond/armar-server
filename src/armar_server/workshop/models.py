"""Models for the metadata embedded in a workshop page.

The Arma Workshop site (``reforger.armaplatform.com``) is a Next.js app; the full
mod metadata is in a ``<script id="__NEXT_DATA__">`` JSON blob at
``props.pageProps.asset``. These models mirror the subset we need (``extra=ignore``
so the site can grow new fields without breaking us).

Note the dependency shape: the dependency's hex id lives at
``dependencies[i].asset.id`` (one level deeper than you'd expect), and transitive
dependencies nest under ``dependencies[i].dependencies``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Scenario(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    # gameId is exactly the "{GUID}Missions/....conf" string the config needs.
    gameId: str
    gameMode: str | None = None
    playerCount: int | None = None


class DepAsset(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str | None = None


class DependencyRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    asset: DepAsset
    version: str | None = None
    dependencies: list[DependencyRef] = []


class Asset(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    currentVersionNumber: str | None = None
    gameVersion: str | None = None
    dependencies: list[DependencyRef] = []
    scenarios: list[Scenario] = []


DependencyRef.model_rebuild()
