"""Tests for the read-only port-intelligence adapter."""

import os
from pathlib import Path

import pytest

from maritime.ingestion.noaa import NoaaConfig, NoaaProvider
from maritime.pipeline_noaa import NOAA_DATASET_KEY, build_port_snapshot
from maritime.port_adapter import (
    PortFeatureAdapter,
    maritime_port_enabled,
)
from maritime.storage.snapshots import SnapshotStore


PORTS_FIXTURE = Path("data/maritime/synthetic/ports_sample.json")
NOAA_FIXTURE = Path("data/maritime/synthetic/noaa_ais_sample.jsonl")


def _build_snapshot(tmp_path):
    if not PORTS_FIXTURE.exists() or not NOAA_FIXTURE.exists():
        pytest.skip("fixtures missing")
    import json
    from maritime.schemas.port import Port
    ports_data = json.loads(PORTS_FIXTURE.read_text(encoding="utf-8"))
    ports = [Port.from_dict(p) for p in ports_data["ports"]]
    cfg = NoaaConfig(mode="local", local_path=str(NOAA_FIXTURE))
    ingestion = NoaaProvider(cfg).fetch()
    store = SnapshotStore(base_dir=tmp_path / "snap")
    build_port_snapshot(ingestion=ingestion, ports=ports, store=store)
    return store


def test_adapter_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "0")
    monkeypatch.delenv("MARITIME_PORT_INTELLIGENCE_ENABLED", raising=False)
    store = _build_snapshot(tmp_path)
    adapter = PortFeatureAdapter(store=store)
    assert maritime_port_enabled() is False
    assert adapter.get_port_snapshot_metadata() is None
    assert adapter.get_ports() == []
    assert adapter.get_port_calls() == []
    assert adapter.get_port_call_count() == 0
    assert adapter.get_port_activity() == []
    assert adapter.get_port_vessel_type_mix() == []
    assert adapter.get_port_call_timeline() == []


def test_adapter_enabled_returns_data(monkeypatch, tmp_path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_PORT_INTELLIGENCE_ENABLED", "1")
    store = _build_snapshot(tmp_path)
    adapter = PortFeatureAdapter(store=store)
    meta = adapter.get_port_snapshot_metadata()
    assert meta is not None
    assert meta["source"] == "MARINE_CADASTRE"
    ports = adapter.get_ports()
    assert len(ports) >= 1
    calls = adapter.get_port_calls()
    assert len(calls) >= 1


def test_adapter_port_calls_filtered_by_port(monkeypatch, tmp_path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_PORT_INTELLIGENCE_ENABLED", "1")
    store = _build_snapshot(tmp_path)
    adapter = PortFeatureAdapter(store=store)
    calls = adapter.get_port_calls(port_id="USLAX")
    assert all(c["port_id"] == "USLAX" for c in calls)


def test_adapter_vessel_history(monkeypatch, tmp_path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_PORT_INTELLIGENCE_ENABLED", "1")
    store = _build_snapshot(tmp_path)
    adapter = PortFeatureAdapter(store=store)
    history = adapter.get_vessel_history("338000001")
    assert len(history) >= 1
    assert all(p["mmsi"] == "338000001" for p in history)


def test_adapter_source_health(monkeypatch, tmp_path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_PORT_INTELLIGENCE_ENABLED", "1")
    store = _build_snapshot(tmp_path)
    adapter = PortFeatureAdapter(store=store)
    health = adapter.get_source_health()
    assert health is not None
    assert "source_status" in health
    assert "quality_status" in health


def test_adapter_port_activity_and_mix(monkeypatch, tmp_path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_PORT_INTELLIGENCE_ENABLED", "1")
    store = _build_snapshot(tmp_path)
    adapter = PortFeatureAdapter(store=store)
    activity = adapter.get_port_activity()
    mix = adapter.get_port_vessel_type_mix()
    timeline = adapter.get_port_call_timeline()
    assert len(activity) >= 1
    assert len(mix) >= 1
    assert len(timeline) >= 1


def test_adapter_safe_when_no_snapshot(monkeypatch, tmp_path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_PORT_INTELLIGENCE_ENABLED", "1")
    store = SnapshotStore(base_dir=tmp_path / "empty")
    adapter = PortFeatureAdapter(store=store)
    # No snapshot on disk; all reads must return empty safely.
    assert adapter.get_port_snapshot_metadata() is None
    assert adapter.get_ports() == []
    assert adapter.get_port_calls() == []
    assert adapter.get_port_call_count() == 0
    assert adapter.get_source_health() is None
    assert adapter.get_vessel_history("338000001") == []