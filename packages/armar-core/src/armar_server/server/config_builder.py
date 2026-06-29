"""Turn the friendly ``AppConfig`` + resolved ``LockFile`` into a ``ServerConfig``."""

from __future__ import annotations

from ..config.models import (
    A2S,
    AppConfig,
    Game,
    GameProperties,
    LockFile,
    ModEntry,
    Rcon,
    ServerConfig,
)


def build_server_config(
    app: AppConfig,
    lock: LockFile,
    *,
    public_address: str | None = None,
) -> ServerConfig:
    """Compose the Reforger JSON config.

    ``public_address`` (when provided) overrides ``app.public_address`` — the CLI
    passes a detected LAN IP here for bridged networking.
    """
    mods = [
        ModEntry(modId=entry.mod_id, name=entry.name, version=entry.version) for entry in lock.mods
    ]

    game_properties = GameProperties(**{"battlEye": app.battleye, **app.game_properties})

    game = Game(
        name=app.name,
        password=app.password,
        passwordAdmin=app.admin_password,
        admins=list(app.admins),
        scenarioId=app.scenario_id,
        maxPlayers=app.max_players,
        visible=app.visible,
        crossPlatform=app.cross_platform,
        gameProperties=game_properties,
        mods=mods,
    )

    rcon = Rcon(password=app.rcon_password, port=app.rcon_port) if app.rcon_enabled else None

    return ServerConfig(
        bindPort=app.bind_port,
        publicAddress=public_address if public_address is not None else app.public_address,
        publicPort=app.public_port,
        a2s=A2S(port=app.a2s_port),
        rcon=rcon,
        game=game,
        operating=dict(app.operating),
    )
