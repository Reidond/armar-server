"""FastAPI app factory + DI wiring for `armar-agentd`.

The factory is the *only* place that knows about the wiring between
settings, token store, job manager, and routes. Tests can build the app
with fakes at this boundary.
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from armar_server.config.settings import AppSettings
from armar_server.contracts import PROTOCOL_VERSION
from armar_server.errors import ArmarError

from .jobs import JobManager
from .routes import config, host, instances, jobs, lifecycle, logs, mods, scenarios
from .security import AgentSettings, TokenStore, make_token_dependency


def create_app(
    *,
    agent_settings: AgentSettings | None = None,
    app_settings: AppSettings | None = None,
    token_store: TokenStore | None = None,
    job_manager: JobManager | None = None,
) -> FastAPI:
    """Build the FastAPI app; everything else is DI-injected."""
    agent_settings = agent_settings or AgentSettings()
    app_settings = app_settings or _default_app_settings(agent_settings)
    token_store = token_store or TokenStore(agent_settings.data_dir / "token")
    job_manager = job_manager or JobManager()

    @asynccontextmanager
    async def _lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        app.state.started_at = datetime.now(UTC)
        app.state.agent_settings = agent_settings
        app.state.app_settings = app_settings
        app.state.token_store = token_store
        app.state.job_manager = job_manager
        app.state.token_dep = make_token_dependency(agent_settings, token_store)
        try:
            yield
        finally:
            pass

    app = FastAPI(
        title="armar-agentd",
        version=str(PROTOCOL_VERSION),
        lifespan=_lifespan,
    )
    app.include_router(host.router)
    app.include_router(instances.router)
    app.include_router(lifecycle.router)
    app.include_router(jobs.router)
    app.include_router(mods.router)
    app.include_router(config.router)
    app.include_router(scenarios.router)
    app.include_router(logs.router)

    @app.exception_handler(ArmarError)
    async def _on_armar_error(_request: Request, exc: ArmarError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": {"type": exc.__class__.__name__, "message": str(exc)}},
        )

    @app.exception_handler(Exception)
    async def _on_unhandled(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": {"type": exc.__class__.__name__, "message": str(exc)}},
        )

    return app


def _default_app_settings(agent_settings: AgentSettings) -> AppSettings:
    base = AppSettings(data_dir=agent_settings.effective_instances_dir().parent)
    return base


def main(argv: list[str] | None = None) -> int:
    """`armar-agentd` entry point. Subcommands:

    - ``serve [--bind HOST:PORT | --uds PATH]`` (also the no-subcommand
      default) → start the FastAPI app via uvicorn
    - ``--protocol-version`` → print the wire protocol version and exit
    - ``install`` → install the systemd --user unit + enable linger
    - ``uninstall`` → remove the systemd --user unit
    - ``token print`` / ``token rotate``
    - ``doctor`` → host readiness checks

    Implementation lives in the bootstrap subpackage; we dispatch here.
    """
    parser = argparse.ArgumentParser(prog="armar-agentd")
    parser.add_argument(
        "--protocol-version",
        action="store_true",
        help="Print the wire protocol version and exit (used by the desktop handshake).",
    )
    sub = parser.add_subparsers(dest="cmd", required=False)
    serve = sub.add_parser("serve", help="Run the FastAPI app via uvicorn.")
    serve.add_argument("--bind", default=None, help="HOST:PORT to listen on (loopback only).")
    serve.add_argument("--uds", default=None, help="Unix-domain socket path (token disabled).")
    sub.add_parser("install")
    sub.add_parser("uninstall")
    sub.add_parser("doctor")
    token = sub.add_parser("token")
    token_sub = token.add_subparsers(dest="token_cmd", required=True)
    token_sub.add_parser("print")
    token_sub.add_parser("rotate")
    args = parser.parse_args(argv)

    if args.protocol_version:
        print(PROTOCOL_VERSION)
        return 0
    if args.cmd in (None, "serve"):
        return _serve(bind=getattr(args, "bind", None), uds=getattr(args, "uds", None))
    if args.cmd == "install":
        from .bootstrap.install import install

        return install()
    if args.cmd == "uninstall":
        from .bootstrap.install import uninstall

        return uninstall()
    if args.cmd == "doctor":
        from .bootstrap.install import doctor

        return doctor()
    if args.cmd == "token":
        from .bootstrap.install import token_print, token_rotate

        return token_print() if args.token_cmd == "print" else token_rotate()  # noqa: S105
    parser.print_help()
    return 1


def _serve(*, bind: str | None = None, uds: str | None = None) -> int:
    import uvicorn

    settings = AgentSettings()
    kwargs = _serve_kwargs(settings, bind=bind, uds=uds)
    if "uds" in kwargs:
        uvicorn.run(
            "armar_agentd.app:create_app",
            factory=True,
            log_level="info",
            uds=str(kwargs["uds"]),
        )
    else:
        uvicorn.run(
            "armar_agentd.app:create_app",
            factory=True,
            log_level="info",
            host=str(kwargs["host"]),
            port=int(kwargs["port"]),
        )
    return 0


def _serve_kwargs(
    settings: AgentSettings, *, bind: str | None = None, uds: str | None = None
) -> dict[str, str | int]:
    """Resolve uvicorn transport kwargs from CLI overrides + settings.

    CLI ``--uds``/``--bind`` win over the configured defaults. This keeps
    the systemd unit (which passes ``serve --bind HOST:PORT`` / ``--uds
    PATH``) and the bare ``armar-agentd`` (settings-driven) on one path.
    Pure so it can be asserted without starting uvicorn.
    """
    if uds:
        return {"uds": uds}
    if bind:
        host, _, port = bind.rpartition(":")
        return {"host": (host or settings.bind_host).strip("[]"), "port": int(port)}
    if settings.uds_path:
        return {"uds": str(settings.uds_path)}
    return {"host": settings.bind_host, "port": settings.bind_port}


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


# Re-export for tests / downstream
__all__ = ["PROTOCOL_VERSION", "create_app", "main"]


# Avoid unused-import noise; the constants are part of the public surface.
_ = json
_ = Path
