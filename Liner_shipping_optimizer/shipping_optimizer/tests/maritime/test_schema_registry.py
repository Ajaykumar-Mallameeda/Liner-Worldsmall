"""Phase 3 — Schema registry tests."""

import pytest

from maritime.schema_registry import SchemaPolicy, SchemaRegistry


def test_default_registry_compatible_with_1_0_0():
    reg = SchemaRegistry.with_defaults()
    assert reg.is_compatible("emodnet_vessel_density", "1.0.0")
    assert reg.is_compatible("noaa_ais_port_intelligence", "1.0.0")
    assert not reg.is_compatible("emodnet_vessel_density", "2.0.0")
    assert not reg.is_compatible("unknown_dataset", "2.0.0")


def test_default_policy_used_for_unknown_dataset():
    reg = SchemaRegistry()
    assert reg.is_compatible("some_new_dataset", "1.0.0")
    assert not reg.is_compatible("some_new_dataset", "2.0.0")


def test_register_policy():
    reg = SchemaRegistry()
    pol = SchemaPolicy(
        dataset="custom",
        compatible_versions=("0.9.0", "1.0.0"),
        current_version="1.0.0",
    )
    reg.register(pol)
    assert reg.is_compatible("custom", "0.9.0")
    assert reg.is_compatible("custom", "1.0.0")
    assert not reg.is_compatible("custom", "1.1.0")


def test_compatible_versions_returns_tuple():
    reg = SchemaRegistry.with_defaults()
    vs = reg.compatible_versions("emodnet_vessel_density")
    assert vs == ("1.0.0",)
    assert isinstance(vs, tuple)


def test_policy_for_unknown_dataset_returns_default():
    reg = SchemaRegistry.with_defaults()
    p = reg.policy_for("zzz")
    assert p.dataset == "__default__"
    assert p.is_compatible("1.0.0")
