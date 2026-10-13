"""End-to-end tests for the NOAA port-intelligence pipeline."""

from pathlib import Path

import pytest

from maritime.ingestion.noaa import NoaaConfig, NoaaProvider
from maritime.pipeline_noaa import (
    NOAA_DATASET_KEY,
    build_port_snapshot,
)
from maritime.port_adapter import (
    NOAA_DATASET_KEY as ADAPTER_DATASET_KEY,
    PortFeatureAdapter,
    load_port_snapshot_from_paths,
)
from maritime.schemas.intelligence import QualityStatus
from maritime.storage.snapshots import SnapshotPaths, SnapshotStore


PORTS_FIXTURE = Path("data/maritime/synthetic/ports_sample.json")
NOAA_FIXTURE = Path("data/maritime/synthetic/noaa_ais_sample.jsonl")


def _load_ports():
    import json
    data = json.loads(PORTS_FIXTURE.read_text(encoding="utf-8"))
    return [Port.from_dict(p) for p in data["ports"]] if False else _ports_alt(data)


def _ports_alt(data):
    from maritime.schemas.port import Port
    return [Port.from_dict(p) for p in data["ports"]]


def test_pipeline_builds_snapshot(tmp_path):
    if not PORTS_FIXTURE.exists() or not NOAA_FIXTURE.exists():
        pytest.skip("fixtures missing")
    ports = _ports_alt(__import__("json").loads(PORTS_FIXTURE.read_text(encoding="utf-8")))
    cfg = NoaaConfig(mode="local", local_path=str(NOAA_FIXTURE))
    ingestion = NoaaProvider(cfg).fetch()
    store = SnapshotStore(base_dir=tmp_path / "snap")
    snap = build_port_snapshot(ingestion=ingestion, ports=ports, store=store)
    assert snap.accepted_records > 0
    assert len(snap.ports) == len(ports)
    assert len(snap.port_calls) > 0
    # All features should be derived.
    assert len(snap.port_activity_features) > 0
    assert len(snap.port_vessel_mix_features) > 0
    # Snapshot written to disk under the canonical dataset key.
    paths = store.latest(NOAA_DATASET_KEY)
    assert paths is not None


def test_pipeline_quality_degraded_when_no_ports(tmp_path):
    if not NOAA_FIXTURE.exists():
        pytest.skip("fixture missing")
    cfg = NoaaConfig(mode="local", local_path=str(NOAA_FIXTURE))
    ingestion = NoaaProvider(cfg).fetch()
    snap = build_port_snapshot(ingestion=ingestion, ports=[], store=None)
    # No ports => degraded (positions were valid)
    assert snap.quality_status == QualityStatus.DEGRADED


def test_pipeline_loads_snapshot_from_disk(tmp_path):
    if not PORTS_FIXTURE.exists() or not NOAA_FIXTURE.exists():
        pytest.skip("fixtures missing")
    ports = _ports_alt(__import__("json").loads(PORTS_FIXTURE.read_text(encoding="utf-8")))
    cfg = NoaaConfig(mode="local", local_path=str(NOAA_FIXTURE))
    ingestion = NoaaProvider(cfg).fetch()
    store = SnapshotStore(base_dir=tmp_path / "snap")
    build_port_snapshot(ingestion=ingestion, ports=ports, store=store)
    paths = store.latest(NOAA_DATASET_KEY)
    assert paths is not None
    loaded = load_port_snapshot_from_paths(paths)
    assert loaded.snapshot_id == paths.snapshot_id
    assert len(loaded.positions) == len(ingestion.records)
    assert len(loaded.port_calls) > 0


def test_pipeline_dataset_keys_match():
    # The pipeline writes under NOAA_DATASET_KEY; the adapter reads the
    # same key. They MUST stay in sync.
    assert NOAA_DATASET_KEY == ADAPTER_DATASET_KEY


def test_pipeline_records_dedup(tmp_path):
    if not PORTS_FIXTURE.exists() or not NOAA_FIXTURE.exists():
        pytest.skip("fixtures missing")
    ports = _ports_alt(__import__("json").loads(PORTS_FIXTURE.read_text(encoding="utf-8")))
    cfg = NoaaConfig(mode="local", local_path=str(NOAA_FIXTURE))
    ingestion = NoaaProvider(cfg).fetch()
    # Duplicate every record to provoke dedup counters.
    ingestion.records = ingestion.records + list(ingestion.records)
    snap = build_port_snapshot(ingestion=ingestion, ports=ports, store=None)
    assert snap.duplicate_records > 0
    assert snap.rejected_records > 0
    # Accepted records remain unchanged.
    unique_ingested = len(set((r.get("mmsi"), r.get("timestamp")) for r in ingestion.records))
    assert snap.accepted_records == unique_ingested


def test_pipeline_no_records_marks_invalid(tmp_path):
    cfg = NoaaConfig(mode="local", local_path=str(NOAA_FIXTURE))
    from maritime.ingestion.base import IngestionResult
    ingestion = IngestionResult(
        source="MARINE_CADASTRE",
        dataset="d",
        dataset_version="0",
        records=[],
        license="CC0",
        attribution="NOAA",
        retrieved_at="2024-06-01T00:00:00+00:00",
        observed_period={"start": "2024-06-01T00:00:00+00:00", "end": "2024-06-01T00:00:00+00:00"},
        source_url="local://empty",
    )
    if PORTS_FIXTURE.exists():
        ports = _ports_alt(__import__("json").loads(PORTS_FIXTURE.read_text(encoding="utf-8")))
    else:
        # The synthetic fixture directory is not shipped with this tree.  What this test checks - an
        # ingestion with ZERO records is INVALID whatever the port list is - needs only some ports, so
        # two inline test ports (clearly labelled, not data) are used instead of failing on the file.
        ports = _ports_alt({"ports": [
            {"port_id": f"TEST_{k}", "name": f"Inline test port {k}", "latitude": 29.0 + k, "longitude": -95.0,
             "radius_nm": 5.0, "port_type": "cargo", "source": "INLINE_TEST", "dataset": "inline_test",
             "dataset_version": "0", "license": "CC0", "attribution": "unit test"} for k in (0, 1)]})
    snap = build_port_snapshot(ingestion=ingestion, ports=ports, store=None)
    assert snap.quality_status == QualityStatus.INVALID
    assert snap.call_count == 0