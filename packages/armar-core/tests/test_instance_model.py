"""Tests for the multi-server instance model."""

from __future__ import annotations

from pathlib import Path

import pytest

from armar_server.config.instance import InstanceSettings, validate_slug
from armar_server.config.ports import NoFreePortsError, PortTriplet, allocate_triplet
from armar_server.config.registry import (
    CURRENT_SCHEMA_VERSION,
    InstanceAlreadyExistsError,
    InstanceManifest,
    InstanceNotFoundError,
    InstanceRegistry,
    InstanceRunningError,
)
from armar_server.config.settings import AppSettings

# ---- validate_slug --------------------------------------------------------


def test_validate_slug_accepts_alphanumeric() -> None:
    assert validate_slug("alpha") == "alpha"
    assert validate_slug("a1b2") == "a1b2"


def test_validate_slug_accepts_hyphens() -> None:
    assert validate_slug("alpha-bravo") == "alpha-bravo"
    assert validate_slug("a-1-b") == "a-1-b"


def test_validate_slug_rejects_too_short() -> None:
    with pytest.raises(ValueError):
        validate_slug("a")
    with pytest.raises(ValueError):
        validate_slug("")


def test_validate_slug_rejects_too_long() -> None:
    with pytest.raises(ValueError):
        validate_slug("a" * 33)


def test_validate_slug_rejects_uppercase() -> None:
    with pytest.raises(ValueError):
        validate_slug("Alpha")


def test_validate_slug_rejects_special_chars() -> None:
    with pytest.raises(ValueError):
        validate_slug("alpha bravo")
    with pytest.raises(ValueError):
        validate_slug("alpha.bravo")
    with pytest.raises(ValueError):
        validate_slug("_alpha")


def test_validate_slug_rejects_reserved() -> None:
    with pytest.raises(ValueError):
        validate_slug("default")
    with pytest.raises(ValueError):
        validate_slug("reforger")
    with pytest.raises(ValueError):
        validate_slug("armar")


# ---- InstanceSettings ------------------------------------------------------


def test_instance_settings_legacy_reproduces_cwd_layout(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    s = InstanceSettings.legacy(base, name="legacy-server")
    assert s.slug == "default"
    assert s.container_name == "armar-reforger"
    assert s.server_dir == tmp_path / "data" / "server"
    assert s.profile_dir == tmp_path / "data" / "profile"
    assert s.config_dir == tmp_path / "data" / "config"
    assert s.game_port == 2001
    assert s.a2s_port == 17777
    assert s.rcon_port == 19999
    assert s.network_mode == "host"


def test_instance_settings_from_base_creates_namespaced_layout(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    s = InstanceSettings.from_base(
        base, slug="alpha", name="Alpha", game_port=2001, a2s_port=17777, rcon_port=19999
    )
    assert s.slug == "alpha"
    assert s.container_name == "armar-alpha"
    assert s.server_dir == tmp_path / "data" / "instances" / "alpha" / "server"
    assert s.profile_dir == tmp_path / "data" / "instances" / "alpha" / "profile"
    assert s.config_dir == tmp_path / "data" / "instances" / "alpha" / "config"


def test_instance_settings_from_base_rejects_invalid_slug(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    with pytest.raises(ValueError):
        InstanceSettings.from_base(
            base, slug="BAD!", name="X", game_port=2001, a2s_port=17777, rcon_port=19999
        )


def test_instance_settings_rejects_unknown_network_mode(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    with pytest.raises(ValueError):
        InstanceSettings.from_base(
            base,
            slug="alpha",
            name="Alpha",
            game_port=2001,
            a2s_port=17777,
            rcon_port=19999,
            network_mode="weird",
        )


# ---- allocate_triplet ------------------------------------------------------


def test_allocate_triplet_first_is_base() -> None:
    triplet = allocate_triplet(set())
    assert triplet == PortTriplet(2001, 17777, 19999)


def test_allocate_triplet_skips_used() -> None:
    used = {2001, 17777, 19999}
    triplet = allocate_triplet(used)
    # Step = 30 ⇒ (2001+30, 17777+30, 19999+30)
    assert triplet == PortTriplet(2031, 17807, 20029)


def test_allocate_triplet_handles_overlap_in_middle() -> None:
    used = {2001, 17777, 19999, 2031, 17807, 20029}
    triplet = allocate_triplet(used)
    assert triplet == PortTriplet(2061, 17837, 20059)


def test_allocate_triplet_respects_custom_bases() -> None:
    triplet = allocate_triplet(set(), base_game=10_000, base_a2s=12_000, base_rcon=14_000)
    assert triplet == PortTriplet(10_000, 12_000, 14_000)


def test_allocate_triplet_raises_when_exhausted() -> None:
    used = {2001, 17777, 19999}
    for n in range(1, 100):
        used.update({2001 + n * 30, 17777 + n * 30, 19999 + n * 30})
    with pytest.raises(NoFreePortsError):
        allocate_triplet(used, max_attempts=10)


# ---- InstanceRegistry ------------------------------------------------------


def test_registry_list_empty(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    reg = InstanceRegistry(base)
    assert reg.list() == []


def test_registry_create_then_show(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    reg = InstanceRegistry(base)
    s = reg.create(slug="alpha", name="Alpha")
    assert (base.instances_dir / "alpha" / "instance.toml").exists()
    shown = reg.show("alpha")
    assert shown.slug == "alpha"
    assert shown.container_name == "armar-alpha"
    assert shown.game_port == s.game_port


def test_registry_rejects_duplicate_slug(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    reg = InstanceRegistry(base)
    reg.create(slug="alpha", name="Alpha")
    with pytest.raises(InstanceAlreadyExistsError):
        reg.create(slug="alpha", name="Other")


def test_registry_rejects_reserved_slug(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    reg = InstanceRegistry(base)
    with pytest.raises(ValueError):
        reg.create(slug="default", name="X")
    with pytest.raises(ValueError):
        reg.create(slug="reforger", name="X")


def test_registry_creates_disjoint_ports(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    reg = InstanceRegistry(base)
    a = reg.create(slug="alpha", name="Alpha")
    b = reg.create(slug="bravo", name="Bravo")
    ports = {a.game_port, a.a2s_port, a.rcon_port, b.game_port, b.a2s_port, b.rcon_port}
    assert len(ports) == 6, f"expected disjoint ports, got {ports}"


def test_registry_explicit_ports_must_be_disjoint(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    reg = InstanceRegistry(base)
    reg.create(slug="alpha", name="Alpha")
    from armar_server.config.registry import InstanceError

    with pytest.raises(InstanceError):
        reg.create(slug="bravo", name="Bravo", game_port=2001, a2s_port=17777, rcon_port=19999)


def test_registry_remove_existing(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    reg = InstanceRegistry(base)
    reg.create(slug="alpha", name="Alpha")
    reg.remove("alpha", running=True)  # skip running check
    assert (base.instances_dir / "alpha").exists() is False


def test_registry_remove_unknown(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    reg = InstanceRegistry(base)
    with pytest.raises(InstanceNotFoundError):
        reg.remove("alpha", running=True)


def test_registry_remove_refuses_running_without_force(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data", runtime="__nonexistent-binary__")
    reg = InstanceRegistry(base)
    reg.create(slug="alpha", name="Alpha")
    # The runtime is missing, so the running check returns False, and the
    # force flag is not required. Test the *opposite* path: fake a "running"
    # detection by monkeypatching the helper.
    reg._is_container_running = lambda _settings: True  # type: ignore[method-assign]
    with pytest.raises(InstanceRunningError):
        reg.remove("alpha")
    reg._is_container_running = lambda _settings: False  # type: ignore[method-assign]
    reg.remove("alpha")


def test_registry_adopt_default_when_no_legacy(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    reg = InstanceRegistry(base)
    assert reg.adopt_default() is None


def test_registry_adopt_default_with_legacy(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    (base.server_dir).mkdir(parents=True)
    reg = InstanceRegistry(base)
    s = reg.adopt_default()
    assert s is not None
    assert s.slug == "default"
    assert (base.instances_dir / "default" / "instance.toml").exists()


def test_registry_adopt_default_refuses_duplicate(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    (base.server_dir).mkdir(parents=True)
    reg = InstanceRegistry(base)
    reg.adopt_default()
    with pytest.raises(InstanceAlreadyExistsError):
        reg.adopt_default()


def test_registry_adopt_default_allocates_fresh_if_legacy_collides(tmp_path: Path) -> None:
    base = AppSettings(data_dir=tmp_path / "data")
    (base.server_dir).mkdir(parents=True)
    reg = InstanceRegistry(base)
    # Pre-create an instance occupying the legacy base triplet.
    reg.create(slug="twin", name="Twin")
    s = reg.adopt_default()
    assert s is not None
    # The adopted instance should NOT use the legacy base triplet if it's
    # still in use by 'twin' (it is, since 'twin' took it).
    # Note: 'twin' took the base, so adopt_default must allocate a fresh one.
    assert s.game_port != 2001 or s.a2s_port != 17777 or s.rcon_port != 19999


# ---- InstanceManifest ------------------------------------------------------


def test_manifest_roundtrip() -> None:
    from datetime import UTC, datetime

    m = InstanceManifest(
        slug="alpha",
        name="Alpha",
        game_port=2001,
        a2s_port=17777,
        rcon_port=19999,
        network_mode="host",
        created_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    again = InstanceManifest.from_toml(m.to_toml())
    assert again == m
    assert again.schema_version == CURRENT_SCHEMA_VERSION
