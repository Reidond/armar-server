"""``armar`` command-line interface.

Thin Typer handlers that wire settings + config to the services. External
dependencies (workshop HTTP client, container runtime) are created here and
injected, so the services themselves stay testable.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config.instance import validate_slug
from .config.loader import (
    load_app_config,
    load_lock,
    render_server_config,
    save_app_config,
    save_lock,
)
from .config.models import LockEntry, LockFile
from .config.registry import (
    InstanceAlreadyExistsError,
    InstanceNotFoundError,
    InstanceRegistry,
    InstanceRunningError,
)
from .config.settings import AppSettings
from .errors import ArmarError, ConfigError
from .logging import setup_logging
from .net import detect_lan_ip
from .server.config_builder import build_server_config
from .server.launcher import build_server_spec, build_steamcmd_spec
from .server.runtime import ContainerRuntime, make_runtime
from .server.systemd import render_docker_service, render_quadlet
from .workshop.client import WORKSHOP_BASE_URL, HttpWorkshopClient, parse_mod_id
from .workshop.parser import parse_asset
from .workshop.resolver import DependencyResolver

console = Console()

app = typer.Typer(
    name="armar",
    help="Run a modded Arma Reforger dedicated server from Workshop URLs.",
    no_args_is_help=True,
    add_completion=False,
)
mods_app = typer.Typer(help="Manage the mod list in server.toml.", no_args_is_help=True)
service_app = typer.Typer(help="Generate systemd units for the server.", no_args_is_help=True)
instance_app = typer.Typer(help="Manage multi-server instances.", no_args_is_help=True)
app.add_typer(mods_app, name="mods")
app.add_typer(service_app, name="service")
app.add_typer(instance_app, name="instance")


_DEFAULT_TOML = """\
# armar-server configuration. Edit by hand or via `armar mods add/remove`.
[server]
name = "My Reforger Server"

# The single scenario to run. Reforger runs ONE scenario (no rotation).
# Find scenario ids for your mods with `armar scenarios`, e.g.
# scenario_id = "{ECC61978EDCC2B5A}Missions/23_Campaign.conf"   # vanilla Conflict (Everon)
scenario_id = ""

# Mods as Workshop URLs (or bare hex ids). `armar resolve` pins versions + deps.
mods = []

# Access control
password = ""           # join password (empty = open)
admin_password = ""     # in-game admin password (no spaces)
admins = []             # Identity/Steam ids
max_players = 64
visible = true
cross_platform = false  # true also allows console players
battleye = true

# Networking (defaults match the Reforger wiki: 2001 game, 17777 a2s, 19999 rcon)
bind_port = 2001
public_address = ""     # leave empty in host-network mode (auto-detected)
public_port = 2001
a2s_port = 17777

# RCON (optional)
rcon_enabled = false
rcon_password = ""      # min 3 chars, no spaces
rcon_port = 19999

# Performance
max_fps = 60
"""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _settings() -> AppSettings:
    return AppSettings()


@contextmanager
def _guard() -> Iterator[None]:
    """Map expected ArmarError failures to a clean message + exit code 1."""
    try:
        yield
    except ArmarError as exc:
        console.print(f"[bold red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc


def _ensure_dirs(settings: AppSettings) -> None:
    for directory in (settings.server_dir, settings.profile_dir, settings.config_dir):
        directory.mkdir(parents=True, exist_ok=True)


def _render_config(settings: AppSettings) -> int:
    """Render server-config.json from server.toml + armar.lock. Returns mod count."""
    cfg = load_app_config(settings.config_file)
    lock = load_lock(settings.lock_file)
    public = cfg.public_address
    if settings.network_mode != "host" and not public:
        public = detect_lan_ip()
    server_config = build_server_config(cfg, lock, public_address=public)
    settings.config_dir.mkdir(parents=True, exist_ok=True)
    settings.rendered_config_path.write_text(render_server_config(server_config), encoding="utf-8")
    if not cfg.scenario_id:
        console.print(
            "[yellow]warning:[/] scenario_id is empty — the server will not start. "
            "Pick one with [bold]armar scenarios[/]."
        )
    return len(server_config.game.mods)


def _install_server(settings: AppSettings, *, validate: bool) -> None:
    runtime = make_runtime(settings)
    settings.server_dir.mkdir(parents=True, exist_ok=True)
    spec = build_steamcmd_spec(settings, validate=validate)
    code = runtime.run(spec)
    if code != 0:
        raise typer.Exit(code=code)


# --------------------------------------------------------------------------- #
# top-level commands
# --------------------------------------------------------------------------- #


def _version_callback(value: bool) -> None:
    if value:
        import sys

        sys.stdout.write(f"armar {__version__}\n")
        sys.stdout.flush()
        raise typer.Exit(code=0)


@app.callback()
def _main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print the armar-core version and exit.",
    ),
) -> None:
    setup_logging(verbose=verbose)


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing config."),
) -> None:
    """Create a starter server.toml."""
    with _guard():
        settings = _settings()
        path = settings.config_file
        if path.exists() and not force:
            raise ConfigError(f"{path} already exists (use --force to overwrite).")
        path.write_text(_DEFAULT_TOML, encoding="utf-8")
        console.print(f"[green]Created[/] {path}")
        console.print("Next: [bold]armar mods add <workshop-url>[/] then [bold]armar resolve[/].")


@app.command()
def resolve() -> None:
    """Fetch mod metadata, resolve dependencies, and write armar.lock."""
    with _guard():
        settings = _settings()
        cfg = load_app_config(settings.config_file)
        if not cfg.mods:
            raise ConfigError("No mods configured. Add some with `armar mods add <url>`.")
        ids = [parse_mod_id(ref) for ref in cfg.mods]
        with HttpWorkshopClient() as client:
            result = DependencyResolver(client).resolve(ids)
        lock = LockFile(
            game_version=result.game_version,
            mods=[
                LockEntry(mod_id=m.mod_id, name=m.name, version=m.version, direct=m.direct)
                for m in result.mods
            ],
        )
        save_lock(settings.lock_file, lock)

        table = Table(title=f"Resolved {len(lock.mods)} mods", show_lines=False)
        table.add_column("mod id", style="cyan", no_wrap=True)
        table.add_column("name")
        table.add_column("version", style="green")
        table.add_column("kind", style="dim")
        for m in lock.mods:
            table.add_row(m.mod_id, m.name, m.version or "latest", "direct" if m.direct else "dep")
        console.print(table)
        direct = sum(1 for m in lock.mods if m.direct)
        console.print(
            f"[green]Wrote[/] {settings.lock_file} "
            f"({direct} direct, {len(lock.mods) - direct} dependencies)."
        )


@app.command()
def config() -> None:
    """Render the Reforger server-config.json from server.toml + armar.lock."""
    with _guard():
        settings = _settings()
        count = _render_config(settings)
        console.print(f"[green]Wrote[/] {settings.rendered_config_path} ({count} mods).")


@app.command()
def scenarios() -> None:
    """List scenario ids advertised by the configured mods (copy into scenario_id)."""
    with _guard():
        settings = _settings()
        cfg = load_app_config(settings.config_file)
        if not cfg.mods:
            console.print("No mods configured.")
            return
        ids = [parse_mod_id(ref) for ref in cfg.mods]
        found = 0
        with HttpWorkshopClient() as client:
            for mod_id in ids:
                asset = parse_asset(client.fetch_page(mod_id))
                for scenario in asset.scenarios:
                    found += 1
                    label = scenario.name or "?"
                    console.print(f"[cyan]{scenario.gameId}[/]  [dim]{asset.name} — {label}[/]")
        if found == 0:
            console.print("No mod-provided scenarios found. Use a vanilla scenario id instead.")


@app.command()
def build() -> None:
    """Build the container image (docker/ context)."""
    with _guard():
        settings = _settings()
        runtime = make_runtime(settings)
        context = Path("docker")
        if not (context / "Dockerfile").exists():
            raise ConfigError("docker/Dockerfile not found. Run armar from the project root.")
        code = runtime.build_image(
            context,
            settings.image,
            build_args={"UID": str(os.getuid()), "GID": str(os.getgid())},
        )
        if code != 0:
            raise typer.Exit(code=code)
        console.print(f"[green]Built[/] image {settings.image}.")


@app.command()
def install(
    no_validate: bool = typer.Option(False, "--no-validate", help="Skip SteamCMD validate."),
) -> None:
    """Install the dedicated server (SteamCMD app 1874900) into data/server."""
    with _guard():
        _install_server(_settings(), validate=not no_validate)
        console.print("[green]Server installed/updated.[/]")


@app.command()
def update(
    no_validate: bool = typer.Option(False, "--no-validate", help="Skip SteamCMD validate."),
) -> None:
    """Update the dedicated server to the latest build (same as install)."""
    with _guard():
        _install_server(_settings(), validate=not no_validate)
        console.print("[green]Server updated.[/]")


@app.command()
def run() -> None:
    """Render config and run the server in the foreground (Ctrl-C to stop)."""
    with _guard():
        settings = _settings()
        _ensure_dirs(settings)
        _render_config(settings)
        cfg = load_app_config(settings.config_file)
        runtime = make_runtime(settings)
        runtime.remove(settings.container_name)
        code = runtime.run(build_server_spec(settings, cfg, detach=False))
        raise typer.Exit(code=code)


@app.command()
def up() -> None:
    """Render config and start the server detached (background)."""
    with _guard():
        settings = _settings()
        _ensure_dirs(settings)
        _render_config(settings)
        cfg = load_app_config(settings.config_file)
        runtime = make_runtime(settings)
        runtime.remove(settings.container_name)
        code = runtime.run(build_server_spec(settings, cfg, detach=True))
        if code != 0:
            raise typer.Exit(code=code)
        console.print(f"[green]Started[/] {settings.container_name}. Logs: [bold]armar logs -f[/].")


@app.command()
def stop() -> None:
    """Stop the running server container."""
    with _guard():
        settings = _settings()
        make_runtime(settings).stop(settings.container_name)
        console.print(f"[green]Stopped[/] {settings.container_name}.")


@app.command()
def status() -> None:
    """Show whether the server container is running."""
    with _guard():
        settings = _settings()
        running = make_runtime(settings).is_running(settings.container_name)
        state = "[green]running[/]" if running else "[red]stopped[/]"
        console.print(f"{settings.container_name}: {state}")


@app.command()
def logs(follow: bool = typer.Option(False, "--follow", "-f", help="Stream logs.")) -> None:
    """Show server container logs."""
    with _guard():
        settings = _settings()
        code = make_runtime(settings).logs(settings.container_name, follow=follow)
        raise typer.Exit(code=code)


@app.command()
def doctor() -> None:
    """Check the environment is ready to install and run the server."""
    with _guard():
        settings = _settings()
        table = Table(title="armar doctor")
        table.add_column("check", style="bold")
        table.add_column("status", no_wrap=True)
        table.add_column("detail", style="dim")

        def row(name: str, ok: bool | None, detail: str) -> None:
            symbol = {True: "[green]ok[/]", False: "[red]fail[/]", None: "[yellow]warn[/]"}[ok]
            table.add_row(name, symbol, detail)

        runtime = make_runtime(settings)
        row(
            "container runtime",
            runtime.is_available(),
            f"{settings.runtime} ({'found' if runtime.is_available() else 'NOT on PATH'})",
        )

        cfg = None
        if settings.config_file.exists():
            try:
                cfg = load_app_config(settings.config_file)
                row("server.toml", True, f"{len(cfg.mods)} mods configured")
            except ArmarError as exc:
                row("server.toml", False, str(exc))
        else:
            row("server.toml", None, "missing — run `armar init`")

        row(
            "scenario_id",
            bool(cfg and cfg.scenario_id),
            "set" if cfg and cfg.scenario_id else "empty — see `armar scenarios`",
        )
        row(
            "armar.lock",
            settings.lock_file.exists() or None,
            "present" if settings.lock_file.exists() else "missing — run `armar resolve`",
        )
        binary = settings.server_dir / settings.server_executable
        row(
            "server installed",
            binary.exists() or None,
            "present" if binary.exists() else "missing — run `armar build` then `armar install`",
        )
        row(
            "rendered config",
            settings.rendered_config_path.exists() or None,
            "present" if settings.rendered_config_path.exists() else "missing — run `armar config`",
        )

        console.print(table)


# --------------------------------------------------------------------------- #
# mods subcommands
# --------------------------------------------------------------------------- #


@mods_app.command("add")
def mods_add(refs: list[str] = typer.Argument(..., help="Workshop URLs or hex ids.")) -> None:
    """Add one or more mods to server.toml."""
    with _guard():
        settings = _settings()
        cfg = load_app_config(settings.config_file)
        existing = {parse_mod_id(ref) for ref in cfg.mods}
        for ref in refs:
            mod_id = parse_mod_id(ref)
            if mod_id in existing:
                console.print(f"[dim]already present:[/] {mod_id}")
                continue
            existing.add(mod_id)
            cfg.mods.append(f"{WORKSHOP_BASE_URL}{mod_id}")
            console.print(f"[green]added[/] {mod_id}")
        save_app_config(settings.config_file, cfg)
        console.print("Run [bold]armar resolve[/] to pin versions and dependencies.")


@mods_app.command("remove")
def mods_remove(refs: list[str] = typer.Argument(..., help="Workshop URLs or hex ids.")) -> None:
    """Remove one or more mods from server.toml."""
    with _guard():
        settings = _settings()
        cfg = load_app_config(settings.config_file)
        targets = {parse_mod_id(ref) for ref in refs}
        before = len(cfg.mods)
        cfg.mods = [ref for ref in cfg.mods if parse_mod_id(ref) not in targets]
        save_app_config(settings.config_file, cfg)
        console.print(f"[green]Removed[/] {before - len(cfg.mods)} mod(s).")


@mods_app.command("list")
def mods_list() -> None:
    """List configured mods."""
    with _guard():
        settings = _settings()
        cfg = load_app_config(settings.config_file)
        if not cfg.mods:
            console.print("No mods configured.")
            return
        for ref in cfg.mods:
            console.print(f"[cyan]{parse_mod_id(ref)}[/]  [dim]{ref}[/]")


# --------------------------------------------------------------------------- #
# service subcommands
# --------------------------------------------------------------------------- #


@service_app.command("install")
def service_install(
    print_only: bool = typer.Option(False, "--print", help="Print the unit instead of writing it."),
) -> None:
    """Generate a systemd unit (Podman Quadlet or Docker .service) for auto-restart."""
    with _guard():
        settings = _settings()
        cfg = load_app_config(settings.config_file)
        runtime: ContainerRuntime = make_runtime(settings)
        spec = build_server_spec(settings, cfg, detach=False)

        if runtime.binary == "podman":
            unit = render_quadlet(spec)
            dest = Path.home() / ".config" / "containers" / "systemd" / "armar.container"
            reload_hint = "systemctl --user daemon-reload && systemctl --user start armar"
        else:
            unit = render_docker_service(runtime, spec)
            dest = Path.home() / ".config" / "systemd" / "user" / "armar.service"
            reload_hint = "systemctl --user daemon-reload && systemctl --user enable --now armar"

        if print_only:
            console.print(unit)
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(unit, encoding="utf-8")
        console.print(f"[green]Wrote[/] {dest}")
        console.print(f"Enable with: [bold]{reload_hint}[/]")


# --------------------------------------------------------------------------- #
# instance subcommands
# --------------------------------------------------------------------------- #


@instance_app.command("list")
def instance_list() -> None:
    """List all instances in the registry."""
    with _guard():
        registry = InstanceRegistry(_settings())
        rows = registry.list()
        if not rows:
            console.print("No instances. Use [bold]armar instance create[/].")
            return
        table = Table(title=f"Instances ({len(rows)})", show_lines=False)
        table.add_column("slug", style="cyan", no_wrap=True)
        table.add_column("name")
        table.add_column("game", justify="right", style="green")
        table.add_column("a2s", justify="right", style="green")
        table.add_column("rcon", justify="right", style="green")
        table.add_column("created", style="dim")
        for m in rows:
            table.add_row(
                m.slug,
                m.name,
                str(m.game_port),
                str(m.a2s_port),
                str(m.rcon_port),
                m.created_at.strftime("%Y-%m-%d %H:%M"),
            )
        console.print(table)


@instance_app.command("show")
def instance_show(slug: str = typer.Argument(..., help="Instance slug.")) -> None:
    """Show a single instance's layout."""
    with _guard():
        try:
            settings = InstanceRegistry(_settings()).show(slug)
        except InstanceNotFoundError:
            raise ConfigError(f"instance {slug!r} not found") from None
        table = Table(title=f"Instance {settings.slug}")
        table.add_column("key", style="bold")
        table.add_column("value")
        table.add_row("slug", settings.slug)
        table.add_row("name", settings.name)
        table.add_row("container_name", settings.container_name)
        table.add_row("server_dir", str(settings.server_dir))
        table.add_row("profile_dir", str(settings.profile_dir))
        table.add_row("config_dir", str(settings.config_dir))
        table.add_row("game_port", str(settings.game_port))
        table.add_row("a2s_port", str(settings.a2s_port))
        table.add_row("rcon_port", str(settings.rcon_port))
        table.add_row("network_mode", settings.network_mode)
        console.print(table)


@instance_app.command("create")
def instance_create(
    name: str = typer.Option(..., "--name", help="Human-readable instance name."),
    slug: str = typer.Option(..., "--slug", help="URL-safe slug (lowercase, hyphens)."),
    network_mode: str = typer.Option("host", "--network-mode", help="host or bridge."),
) -> None:
    """Create a new instance (auto-allocates a port triplet)."""
    with _guard():
        try:
            validate_slug(slug)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        try:
            settings = InstanceRegistry(_settings()).create(
                slug=slug, name=name, network_mode=network_mode
            )
        except InstanceAlreadyExistsError as exc:
            raise ConfigError(str(exc)) from exc
        console.print(
            f"[green]Created[/] {settings.slug} "
            f"(game={settings.game_port} a2s={settings.a2s_port} rcon={settings.rcon_port}, "
            f"container={settings.container_name})"
        )


@instance_app.command("remove")
def instance_remove(
    slug: str = typer.Argument(..., help="Instance slug."),
    force: bool = typer.Option(False, "--force", help="Skip the 'is running' check."),
) -> None:
    """Remove an instance's directory."""
    with _guard():
        registry = InstanceRegistry(_settings())
        try:
            registry.remove(slug, running=force)
        except InstanceNotFoundError:
            raise ConfigError(f"instance {slug!r} not found") from None
        except InstanceRunningError as exc:
            raise ConfigError(str(exc)) from exc
        console.print(f"[green]Removed[/] {slug}.")


@instance_app.command("adopt-default")
def instance_adopt_default() -> None:
    """Migrate the legacy cwd single-server install into the registry."""
    with _guard():
        try:
            settings = InstanceRegistry(_settings()).adopt_default()
        except InstanceAlreadyExistsError as exc:
            raise ConfigError(str(exc)) from exc
        if settings is None:
            console.print(
                "[yellow]No legacy install found[/] (data/server missing); nothing to adopt."
            )
            return
        console.print(
            f"[green]Adopted[/] {settings.slug} "
            f"(game={settings.game_port} a2s={settings.a2s_port} rcon={settings.rcon_port})"
        )


if __name__ == "__main__":
    app()
