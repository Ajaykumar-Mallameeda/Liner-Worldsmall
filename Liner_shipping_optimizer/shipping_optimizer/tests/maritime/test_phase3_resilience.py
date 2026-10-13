"""Phase 3 — Resilience integration tests.

Covers cross-cutting concerns:
    * no network imports in the resilience core
    * no optimizer import in the resilience core
    * feature flag OFF = zero I/O
    * concurrent reads are safe
    * bounded retry is honoured (no infinite loops)
    * previous-good-snapshot preservation on failure
"""

import hashlib
import json
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from maritime import telemetry
from maritime.fallback_resolver import FallbackTier
from maritime.freshness_policy import FreshnessState
from maritime.safe_feature_adapter import (
    EMODNET_DATASET_KEY,
    SafeFeatureAdapter,
)
from maritime.snapshot_publisher import (
    canonical_json_bytes,
    publish_json,
    publish_jsonl,
)


def _manifest_self_checksum(manifest: dict) -> str:
    body = dict(manifest)
    body.pop("checksum_manifest", None)
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def _publish_snapshot(root, dataset, snapshot_id, *, created_at, quality=0.9):
    snap = root / dataset / snapshot_id
    snap.mkdir(parents=True, exist_ok=True)
    summary = publish_jsonl(snap / "traffic_density.jsonl", [{"id": 1}])
    manifest = {
        "schema_version": "1.0.0",
        "snapshot_id": snapshot_id,
        "dataset": dataset,
        "source": "TEST",
        "created_at": created_at.isoformat(),
        "checksum_records": summary.sha256,
        "checksum_manifest": "",
    }
    manifest["checksum_manifest"] = _manifest_self_checksum(manifest)
    publish_json(snap / "manifest.json", manifest)
    metadata = {
        "snapshot_id": snapshot_id,
        "source": "TEST",
        "dataset": dataset,
        "created_at": created_at.isoformat(),
        "schema_version": "1.0.0",
        "record_count": 1,
        "accepted_records": 1,
        "rejected_records": 0,
        "quality_score": quality,
        "source_health": {
            "source": "TEST", "status": "available",
            "last_check_at": created_at.isoformat(),
            "last_success_at": created_at.isoformat(),
            "last_failure_at": None,
            "consecutive_failures": 0, "notes": "",
        },
    }
    publish_json(snap / "metadata.json", metadata)
    return snap


# --------------------------------------------------------------------
# Network isolation
# --------------------------------------------------------------------

RESILIENCE_MODULES = [
    "maritime.snapshot_publisher",
    "maritime.snapshot_verifier",
    "maritime.schema_registry",
    "maritime.freshness_policy",
    "maritime.fallback_resolver",
    "maritime.snapshot_rollback",
    "maritime.safe_feature_adapter",
]


@pytest.mark.parametrize("modname", RESILIENCE_MODULES)
def test_phase3_modules_have_no_network_imports(modname):
    import ast
    import importlib.util

    spec = importlib.util.find_spec(modname)
    assert spec is not None and spec.origin is not None
    src = Path(spec.origin).read_text(encoding="utf-8")
    tree = ast.parse(src, filename=spec.origin)
    forbidden = {"urllib", "requests", "httpx", "aiohttp", "socket"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden, (
                    f"{modname} imports network module {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden:
                pytest.fail(f"{modname} imports network module {node.module}")


# --------------------------------------------------------------------
# Optimizer isolation
# --------------------------------------------------------------------

@pytest.mark.parametrize("modname", RESILIENCE_MODULES)
def test_phase3_modules_do_not_import_optimizer(modname):
    import ast
    import importlib.util

    spec = importlib.util.find_spec(modname)
    src = Path(spec.origin).read_text(encoding="utf-8")
    tree = ast.parse(src, filename=spec.origin)
    forbidden_roots = {
        "src", "src.optimization", "src.agents", "src.pipeline",
        "src.validation", "src.llm", "src.decomposition", "src.data",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in forbidden_roots or alias.name.startswith("src."):
                    pytest.fail(f"{modname} imports optimizer module {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module.startswith("src.") or node.module.split(".")[0] in forbidden_roots):
                pytest.fail(f"{modname} imports optimizer module {node.module}")


# --------------------------------------------------------------------
# Feature flag OFF
# --------------------------------------------------------------------

def test_flag_off_no_io(monkeypatch, tmp_path: Path):
    """When the master flag is OFF, no snapshot is even read."""
    monkeypatch.delenv("MARITIME_INTELLIGENCE_ENABLED", raising=False)
    # Place a valid snapshot to make sure the adapter doesn't read it
    now = datetime.now(tz=timezone.utc)
    _publish_snapshot(tmp_path, EMODNET_DATASET_KEY, "x",
                      created_at=now - timedelta(hours=1))
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    res = adapter.get_traffic_snapshot()
    assert res.decision.tier == FallbackTier.EMPTY
    # records must be empty because the flag is OFF.
    assert res.records == []


def test_flag_off_telemetry_not_emitted(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("MARITIME_INTELLIGENCE_ENABLED", raising=False)
    telemetry.reset_events()
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    adapter.get_traffic_snapshot()
    # The safe adapter does not emit maritime_snapshot_read when the flag is
    # OFF; that's part of the "no I/O, no side-effects" guarantee.
    events = [e["event"] for e in telemetry.get_events()]
    assert "maritime_snapshot_read" not in events


# --------------------------------------------------------------------
# Concurrent reads
# --------------------------------------------------------------------

def test_concurrent_reads_safe(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "1")
    now = datetime.now(tz=timezone.utc)
    _publish_snapshot(tmp_path, EMODNET_DATASET_KEY, "concurrent-1",
                      created_at=now - timedelta(hours=1))
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)

    results = []
    errors = []

    def worker():
        try:
            r = adapter.get_traffic_snapshot()
            results.append(r)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(results) == 8
    # All results must agree on tier
    tiers = {r.decision.tier for r in results}
    assert tiers == {FallbackTier.FRESH}


# --------------------------------------------------------------------
# Repeated failure (no infinite loop, no retry storm)
# --------------------------------------------------------------------

def test_repeated_failure_returns_empty(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "1")
    # Empty store -> resolver will return EMPTY every call
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    for _ in range(20):
        r = adapter.get_traffic_snapshot()
        assert r.decision.tier == FallbackTier.EMPTY


# --------------------------------------------------------------------
# Previous good snapshot preservation
# --------------------------------------------------------------------

def test_publish_failure_preserves_previous(monkeypatch, tmp_path: Path):
    """Publishing a new snapshot must never destroy the previous known-good."""
    from maritime.snapshot_publisher import (
        ChecksumMismatchError,
        publish_json,
    )
    target = tmp_path / "manifest.json"
    # Publish a good baseline.
    r1 = publish_json(target, {"v": 1})
    original_sha = r1.sha256
    original_size = r1.size_bytes
    # Try to publish with a deliberately-wrong checksum.
    with pytest.raises(ChecksumMismatchError):
        publish_json(target, {"v": 2}, expected_sha256="0" * 64)
    # Original file untouched.
    assert target.exists()
    assert _sha256(target) == original_sha
    assert target.stat().st_size == original_size
    # And the contents are still the original.
    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 1}


def _sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------
# Telemetry surface completeness
# --------------------------------------------------------------------

def test_telemetry_event_names_are_documented(monkeypatch, tmp_path: Path):
    """The Phase 3 events use the maritime_ prefix; they never collide with
    the /ws/pipeline event names."""
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_TRAFFIC_ENABLED", "1")
    now = datetime.now(tz=timezone.utc)
    _publish_snapshot(tmp_path, EMODNET_DATASET_KEY, "x",
                      created_at=now - timedelta(hours=1))
    telemetry.reset_events()
    adapter = SafeFeatureAdapter(snapshot_root=tmp_path)
    adapter.get_traffic_snapshot()
    events = [e["event"] for e in telemetry.get_events()]
    assert all(ev.startswith("maritime_") for ev in events)
    # The pipeline events must never be present in maritime telemetry.
    for forbidden in (
        "initial_state", "pipeline_started", "stage_started",
        "stage_completed", "pipeline_completed", "pipeline_error",
    ):
        assert forbidden not in events
