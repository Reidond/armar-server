"""Pydantic models.

Two layers:

* ``AppConfig`` — the friendly, hand-editable ``server.toml`` the user maintains
  (snake_case, sensible defaults).
* ``ServerConfig`` and friends — an exact mirror of the Arma Reforger dedicated
  server JSON config (camelCase field names == JSON keys, so serialization is a
  straight ``model_dump``). Schema per the Bohemia Interactive wiki
  (``Arma_Reforger:Server_Config``).
* ``LockFile`` — the pinned, dependency-resolved mod set produced by ``resolve``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Reforger server JSON config (camelCase fields map 1:1 to JSON keys)
# --------------------------------------------------------------------------- #


class ModEntry(BaseModel):
    """One entry of ``game.mods[]``.

    ``modId`` is the hex GUID from the workshop URL. ``name`` is a human-readable
    comment only. ``version`` omitted => server pulls the latest.
    """

    model_config = ConfigDict(extra="forbid")

    modId: str
    name: str | None = None
    version: str | None = None
    required: bool | None = None


class A2S(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str = "0.0.0.0"  # noqa: S104 — default A2S bind (server config, not a server bind)
    port: int = 17777


class Rcon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str = "0.0.0.0"  # noqa: S104 — default RCON bind (server config, not a server bind)
    port: int = 19999
    password: str
    permission: str = "admin"  # "admin" | "monitor"
    maxClients: int = 16
    blacklist: list[str] = Field(default_factory=list)
    whitelist: list[str] = Field(default_factory=list)


class GameProperties(BaseModel):
    # Only fastValidation + battlEye are emitted by default; everything else is
    # omitted (None) so the server uses its own defaults. This avoids sending
    # values that trip version-specific JSON-schema limits (e.g. the 1.7.x schema
    # rejects serverMinGrassDistance=0 even though the wiki template shows it).
    # extra="allow" lets advanced users pass through any field via game_properties
    # (e.g. missionHeader, persistence).
    model_config = ConfigDict(extra="allow")

    # MUST stay true for any public/internet server (per BI wiki).
    fastValidation: bool = True
    battlEye: bool = True
    serverMaxViewDistance: int | None = None
    serverMinGrassDistance: int | None = None
    networkViewDistance: int | None = None
    disableThirdPerson: bool | None = None
    VONDisableUI: bool | None = None
    VONDisableDirectSpeechUI: bool | None = None
    VONCanTransmitCrossFaction: bool | None = None


class Game(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = ""
    password: str = ""
    passwordAdmin: str = ""
    admins: list[str] = Field(default_factory=list)
    # The single scenario to run (no rotation supported by Reforger).
    scenarioId: str = ""
    maxPlayers: int = 64
    visible: bool = True
    crossPlatform: bool = False
    # Omitted by default: the wiki recommends driving crossplay via crossPlatform
    # alone and leaving supportedPlatforms undefined.
    supportedPlatforms: list[str] | None = None
    gameProperties: GameProperties = Field(default_factory=GameProperties)
    modsRequiredByDefault: bool = True
    mods: list[ModEntry] = Field(default_factory=list)


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bindAddress: str = ""
    bindPort: int = 2001
    publicAddress: str = ""
    publicPort: int = 2001
    a2s: A2S = Field(default_factory=A2S)
    rcon: Rcon | None = None
    game: Game = Field(default_factory=Game)
    operating: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Friendly user config (server.toml)
# --------------------------------------------------------------------------- #


class AppConfig(BaseModel):
    """User-maintained ``server.toml`` (under a ``[server]`` table)."""

    model_config = ConfigDict(extra="forbid")

    # identity / scenario
    name: str = "My Reforger Server"
    scenario_id: str = ""
    # top-level mods: workshop URLs or bare hex ids
    mods: list[str] = Field(default_factory=list)
    # networking
    bind_port: int = 2001
    public_address: str = ""  # "" => auto-detect LAN IP when rendering
    public_port: int = 2001
    a2s_port: int = 17777
    # access control
    password: str = ""
    admin_password: str = ""
    admins: list[str] = Field(default_factory=list)
    max_players: int = 64
    visible: bool = True
    cross_platform: bool = False
    battleye: bool = True
    # rcon
    rcon_enabled: bool = False
    rcon_password: str = ""
    rcon_port: int = 19999
    # runtime
    max_fps: int = 60
    # advanced passthrough (merged verbatim into the JSON)
    game_properties: dict[str, Any] = Field(default_factory=dict)
    operating: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Lock file (pinned, dependency-resolved mod set)
# --------------------------------------------------------------------------- #


class LockEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mod_id: str  # hex GUID, uppercase
    name: str
    version: str | None = None  # pinned currentVersionNumber
    direct: bool = False  # True if user-listed (vs pulled in as a dependency)


class LockFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    generated_with: str = "armar-server"
    game_version: str | None = None  # highest mod gameVersion seen (informational)
    mods: list[LockEntry] = Field(default_factory=list)
