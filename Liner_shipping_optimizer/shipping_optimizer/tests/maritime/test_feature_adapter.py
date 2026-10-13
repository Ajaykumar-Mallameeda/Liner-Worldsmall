"""Tests for the read-only feature adapter."""

import os
from pathlib import Path

import pytest

from maritime.feature_adapter import (
    FeatureAdapter,
    maritime_intelligence_enabled,
    maritime_traffic_enabled,
)
from maritime.pipeline import build_snapshot
from maritime.ingestion.emodnet import EmodnetProvider, EmodnetConfig
from maritime.storage.snapshots import SnapshotStore

FIXTURE = Path("data/maritime/synthetic/emodnet_vessel_density_sample.json")


@pytest.fixture
def enabled_env(monkeypatch):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "1")
    yield


@pytest.fixture
def prepared(enabled_env, tmp_path):
    if not FIXTURE.exists():
        pytest.skip(f"fixture missing: {FIXTURE}")
    store = SnapshotStore(base_dir=tmp_path / "snap")
    cfg = EmodnetConfig(mode="local", local_path=str(FIXTURE))
    provider = EmodnetProvider(cfg)
    ingestion = provider.fetch()
    build_snapshot(ingestion, store=store)
    return store


def test_flags_default_off(monkeypatch):
    monkeypatch.delenv("MARITIME_INTELLIGENCE_ENABLED", raising=False)
    monkeypatch.delenv("MARITIME_TRAFFIC_ENABLED", raising=False)
    assert maritime_intelligence_enabled() is False
    assert maritime_traffic_enabled() is False


def test_flags_enabled_with_env(monkeypatch):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "1")
    assert maritime_intelligence_enabled() is True
    assert maritime_traffic_enabled() is True


def test_flags_off_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "0")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "0")
    store = SnapshotStore(base_dir=tmp_path / "snap")
    adapter = FeatureAdapter(store=store)
    assert adapter.get_snapshot_metadata() is None
    assert adapter.get_traffic_snapshot() == []
    assert adapter.get_density_at(0, 0) == {}
    assert adapter.get_hotspots() == []
    assert adapter.get_source_health() is None


def test_adapter_loads_snapshot_when_enabled(prepared):
    adapter = FeatureAdapter(store=prepared)
    meta = adapter.get_snapshot_metadata()
    assert meta is not None
    assert meta["record_count"] == 10
    feats = adapter.get_traffic_snapshot()
    assert len(feats) > 0
    types = {f["feature_type"] for f in feats}
    assert "traffic_density" in types
    assert "cargo_density" in types
    assert "tanker_density" in types


def test_adapter_density_at_point(prepared):
    adapter = FeatureAdapter(store=prepared)
    d = adapter.get_density_at(31.23, 121.47, radius_deg=1.0)
    assert "traffic_density" in d
    assert d["traffic_density"] > 0.0


def test_adapter_route_density(prepared):
    adapter = FeatureAdapter(store=prepared)
    rd = adapter.get_route_density([(31.23, 121.47), (22.32, 114.17), (1.29, 103.85)])
    assert "traffic_density" in rd
    assert 0.0 <= rd["traffic_density"] <= 1.0


def test_adapter_does_not_call_network(monkeypatch, tmp_path):
    """Adapter must not import or call network code."""
    import maritime.feature_adapter as fa
    src = Path(fa.__file__).read_text(encoding="utf-8")
    for forbidden in ("urllib.request", "urllib.error", "requests.", "httpx.", "aiohttp.", "socket."):
        assert forbidden not in src, f"feature_adapter references {forbidden}"


def test_adapter_returns_empty_when_no_snapshot(enabled_env, tmp_path):
    store = SnapshotStore(base_dir=tmp_path / "empty")
    adapter = FeatureAdapter(store=store)
    assert adapter.get_snapshot_metadata() is None
    assert adapter.get_traffic_snapshot() == []
    assert adapter.get_source_health() is None
