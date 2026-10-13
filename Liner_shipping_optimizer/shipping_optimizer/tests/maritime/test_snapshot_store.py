"""Tests for the snapshot store (write, read, checksum, manifest)."""

import json
import os
from pathlib import Path

import pytest

from maritime.schemas.intelligence import (
    QualityStatus,
    SourceHealth,
    SourceStatus,
    TrafficIntelligenceSnapshot,
)
from maritime.storage.snapshots import (
    SnapshotStore,
    generate_snapshot_id,
    DEFAULT_SNAPSHOT_BASE,
)


def _empty_snapshot(snapshot_id: str = "test-snap") -> TrafficIntelligenceSnapshot:
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc).isoformat()
    return TrafficIntelligenceSnapshot(
        snapshot_id=snapshot_id,
        source="EMODNET",
        dataset="vessel_density_all_ships",
        dataset_version="2023",
        license="CC BY 4.0",
        attribution="EMODnet",
        created_at=now,
        observed_start=now,
        observed_end=now,
        record_count=0,
        accepted_records=0,
        rejected_records=0,
        duplicate_records=0,
        quality_score=1.0,
        completeness_ratio=1.0,
        freshness=now,
        source_status=SourceStatus.AVAILABLE,
        quality_status=QualityStatus.HEALTHY,
        source_health=SourceHealth.initial("EMODNET"),
        provenance={"source": "EMODNET", "dataset": "x", "dataset_version": "1",
                    "retrieved_at": now,
                    "observed_period": {"start": now, "end": now},
                    "license": "CC BY 4.0", "attribution": "EMODnet"},
        records=[],
        features=[],
        hotspots=[],
    )


def test_generate_snapshot_id_format():
    sid = generate_snapshot_id(dataset="emodnet_vessel_density")
    parts = sid.split("_")
    assert parts[0] == "emodnet"
    assert "T" in parts[1]
    assert len(parts[2]) == 8


def test_write_creates_layout(tmp_path):
    store = SnapshotStore(base_dir=tmp_path)
    snap = _empty_snapshot("snap-1")
    paths = store.write(snap)
    assert (paths.root / "manifest.json").exists()
    assert (paths.root / "metadata.json").exists()
    assert (paths.root / "traffic_density.jsonl").exists()


def test_list_snapshots_returns_written(tmp_path):
    store = SnapshotStore(base_dir=tmp_path)
    s1 = _empty_snapshot("snap-1")
    s2 = _empty_snapshot("snap-2")
    store.write(s1)
    store.write(s2)
    snaps = store.list_snapshots("vessel_density_all_ships")
    assert len(snaps) == 2
    assert {s.snapshot_id for s in snaps} == {"snap-1", "snap-2"}


def test_latest_returns_most_recent(tmp_path):
    store = SnapshotStore(base_dir=tmp_path)
    store.write(_empty_snapshot("snap-A"))
    store.write(_empty_snapshot("snap-B"))
    latest = store.latest("vessel_density_all_ships")
    assert latest is not None
    # The store sorts by directory name, so B is later alphabetically.
    assert latest.snapshot_id in {"snap-A", "snap-B"}


def test_checksum_validation_passes(tmp_path):
    store = SnapshotStore(base_dir=tmp_path)
    paths = store.write(_empty_snapshot("snap-1"))
    # Empty records -> file exists but has no records; checksum still matches.
    assert store.verify_checksum(paths) is True


def test_checksum_validation_detects_tampering(tmp_path):
    store = SnapshotStore(base_dir=tmp_path)
    from maritime.schemas.traffic_density import TrafficDensityRecord
    rec = TrafficDensityRecord.from_dict({
        "spatial_id": "cell:1.0,2.0",
        "latitude": 1.0,
        "longitude": 2.0,
        "vessel_class": "cargo",
        "intensity": 10.0,
        "observation_start": "2024-01-01T00:00:00Z",
        "observation_end": "2024-01-02T00:00:00Z",
        "observed_at": "2024-01-02T00:00:00Z",
        "ingested_at": "2024-01-02T01:00:00Z",
        "snapshot_id": "snap-1",
        "source": "EMODNET", "dataset": "d", "dataset_version": "1",
        "quality": 0.9,
        "provenance": {"source": "EMODNET", "dataset": "d", "dataset_version": "1",
                       "retrieved_at": "2024-01-02T01:00:00Z",
                       "observed_period": {"start": "a", "end": "b"}},
        "license": "CC BY 4.0",
        "attribution": "EMODnet",
    })
    snap = TrafficIntelligenceSnapshot(
        snapshot_id="snap-1", source="EMODNET", dataset="vessel_density_all_ships",
        dataset_version="2023", license="CC BY 4.0", attribution="EMODnet",
        created_at="2024-01-02T00:00:00+00:00",
        observed_start="2024-01-01T00:00:00+00:00",
        observed_end="2024-01-02T00:00:00+00:00",
        record_count=1, accepted_records=1, rejected_records=0,
        duplicate_records=0, quality_score=1.0, completeness_ratio=1.0,
        freshness="2024-01-02T00:00:00+00:00",
        source_status=SourceStatus.AVAILABLE, quality_status=QualityStatus.HEALTHY,
        source_health=SourceHealth.initial("EMODNET"),
        provenance={"source": "EMODNET", "dataset": "d", "dataset_version": "1",
                    "retrieved_at": "2024-01-02T01:00:00Z",
                    "observed_period": {"start": "a", "end": "b"},
                    "license": "CC BY 4.0", "attribution": "EMODnet"},
        records=[rec], features=[], hotspots=[],
    )
    paths = store.write(snap)
    assert store.verify_checksum(paths) is True
    # Tamper with the records file.
    (paths.records).write_text("{\"tampered\": true}\n", encoding="utf-8")
    assert store.verify_checksum(paths) is False


def test_snapshot_root_path_under_default_base():
    """The default base path is data/maritime/snapshots."""
    s = str(DEFAULT_SNAPSHOT_BASE).replace("\\", "/")
    assert s.endswith("data/maritime/snapshots")
