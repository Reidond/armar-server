"""Typed exception hierarchy for armar-server.

Services raise these so the CLI can map them to clean, user-facing messages
instead of leaking tracebacks for expected failure modes.
"""

from __future__ import annotations


class ArmarError(Exception):
    """Base class for all armar-server errors."""


class ConfigError(ArmarError):
    """Invalid or missing configuration / lock file."""


class WorkshopError(ArmarError):
    """Problem talking to or parsing the Arma Workshop."""


class WorkshopFetchError(WorkshopError):
    """Network-level failure fetching a workshop page."""


class WorkshopParseError(WorkshopError):
    """A workshop page could not be parsed into mod metadata."""


class ContainerError(ArmarError):
    """Container runtime failure."""


class RuntimeNotFoundError(ContainerError):
    """The configured container runtime (podman/docker) is not installed."""
