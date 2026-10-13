"""Phase 6 — Congestion intelligence layer tests.

Covers:

* Canonical CongestionRecord schema (range checks, round-trip,
  optional fields, rejection cases).
* Deterministic congestion model (score, level, confidence,
  explainability, missing-input handling).
* Congestion orchestrator (disabled by default, synthetic fallback,
  publication, telemetry).
* Read-only FeatureAdapter (no network, empty, at, port, route,
  hotspots, summary).
* Network isolation (congestion package must not import
  urllib / socket; optimizer must not import congestion).
* Feature-flag semantics (default OFF).
* Golden regression invariant for ``pipeline_output.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import urllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest import mock

import pytest


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ts() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _valid_record_kwargs(**overrides) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "record_id": "cong-test-1",
        "entity_id": "port:norfolk",
        "entity_type": "port",
        "latitude": 36.85,
        "longitude": -76.29,
        "observed_at": _ts(),
        "computed_at": _ts(),
        "congestion_score": 0.42,
        "congestion_level": "moderate",
        "confidence": 0.7,
        "freshness_state": "available",
        "source": "derived",
        "dataset": "maritime_congestion",
        "dataset_version": "1.0.0",
        "license": "derived",
        "attribution": "Derived from EMODnet + NOAA + NOAA NWS + Digitraffic",
        "commercial_safe": True,
        "provenance": {"computation_version": "1.0.0"},
        "components": {"traffic": 0.5, "port_pressure": 0.4, "weather_risk": 0.2},
        "missing_inputs": (),
        "synthetic": True,
        "computation_version": "1.0.0",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------
# 1. Schema tests
# --------------------------------------------------------------------


class TestCongestionRecordSchema:
    def test_valid_record_round_trip(self):
        from maritime.schemas.congestion import CongestionRecord
        d = _valid_record_kwargs()
        rec = CongestionRecord.from_dict(d)
        assert rec.congestion_score == 0.42
        assert rec.congestion_level == "moderate"
        out = rec.to_dict()
        assert out["entity_id"] == "port:norfolk"
        assert out["components"]["traffic"] == 0.5
        # Round-trip: from_dict(to_dict()) is stable
        rec2 = CongestionRecord.from_dict(out)
        assert rec2.congestion_score == rec.congestion_score
        assert rec2.entity_id == rec.entity_id

    def test_invalid_latitude_rejected(self):
        from maritime.schemas.congestion import CongestionRecord
        with pytest.raises(ValueError):
            CongestionRecord.from_dict(_valid_record_kwargs(latitude=999.0))

    def test_invalid_longitude_rejected(self):
        from maritime.schemas.congestion import CongestionRecord
        with pytest.raises(ValueError):
            CongestionRecord.from_dict(_valid_record_kwargs(longitude=-200.0))

    def test_invalid_score_rejected(self):
        from maritime.schemas.congestion import CongestionRecord
        with pytest.raises(ValueError):
            CongestionRecord.from_dict(_valid_record_kwargs(congestion_score=1.5))
        with pytest.raises(ValueError):
            CongestionRecord.from_dict(_valid_record_kwargs(congestion_score=-0.01))

    def test_invalid_confidence_rejected(self):
        from maritime.schemas.congestion import CongestionRecord
        with pytest.raises(ValueError):
            CongestionRecord.from_dict(_valid_record_kwargs(confidence=1.5))

    def test_invalid_level_rejected(self):
        from maritime.schemas.congestion import CongestionRecord
        with pytest.raises(ValueError):
            CongestionRecord.from_dict(_valid_record_kwargs(congestion_level="extreme"))

    def test_invalid_entity_type_rejected(self):
        from maritime.schemas.congestion import CongestionRecord
        with pytest.raises(ValueError):
            CongestionRecord.from_dict(_valid_record_kwargs(entity_type="moon"))

    def test_immutability(self):
        from maritime.schemas.congestion import CongestionRecord
        rec = CongestionRecord.from_dict(_valid_record_kwargs())
        with pytest.raises(Exception):
            rec.congestion_score = 0.9  # type: ignore[misc]

    def test_freshness_state_enum(self):
        from maritime.schemas.congestion import CongestionRecord
        with pytest.raises(ValueError):
            CongestionRecord.from_dict(_valid_record_kwargs(freshness_state="bogus"))

    def test_missing_required_string(self):
        from maritime.schemas.congestion import CongestionRecord
        d = _valid_record_kwargs()
        d["entity_id"] = ""
        with pytest.raises(ValueError):
            CongestionRecord.from_dict(d)

    def test_optional_fields_none_accepted(self):
        from maritime.schemas.congestion import CongestionRecord
        d = _valid_record_kwargs(
            vessel_count=None, traffic_density=None, port_call_count=None,
            utilization_proxy=None, weather_quality=None, weather_risk_factor=None,
        )
        rec = CongestionRecord.from_dict(d)
        assert rec.vessel_count is None
        assert rec.traffic_density is None

    def test_components_value_rejected_if_nan(self):
        from maritime.schemas.congestion import CongestionRecord
        d = _valid_record_kwargs(components={"traffic": float("nan")})
        with pytest.raises(ValueError):
            CongestionRecord.from_dict(d)

    def test_synthetic_bool_required(self):
        from maritime.schemas.congestion import CongestionRecord
        # Pass an explicit non-bool; we expect from_dict to reject it
        # (the schema is strict: only True/False are accepted).
        d = _valid_record_kwargs()
        d["synthetic"] = "yes"  # non-bool
        with pytest.raises(ValueError):
            CongestionRecord.from_dict(d)

    def test_level_for_score_bands(self):
        from maritime.schemas.congestion import level_for_score, CongestionLevel
        assert level_for_score(0.0) == CongestionLevel.LOW
        assert level_for_score(0.39) == CongestionLevel.LOW
        assert level_for_score(0.40) == CongestionLevel.MODERATE
        assert level_for_score(0.64) == CongestionLevel.MODERATE
        assert level_for_score(0.65) == CongestionLevel.HIGH
        assert level_for_score(0.84) == CongestionLevel.HIGH
        assert level_for_score(0.85) == CongestionLevel.SEVERE
        assert level_for_score(1.0) == CongestionLevel.SEVERE

    def test_level_for_score_out_of_range(self):
        from maritime.schemas.congestion import level_for_score
        with pytest.raises(ValueError):
            level_for_score(1.1)
        with pytest.raises(ValueError):
            level_for_score(-0.1)


# --------------------------------------------------------------------
# 2. Model tests
# --------------------------------------------------------------------


class TestCongestionModel:
    def test_deterministic(self):
        from maritime.congestion.model import (
            CongestionSignals, evaluate_congestion, CongestionModelConfig,
        )
        sig = CongestionSignals(
            entity_type="port", latitude=10.0, longitude=10.0,
            observed_at=_ts(),
            traffic_density=0.7, cargo_density=0.5, tanker_density=0.4,
            port_call_count=20, utilization_proxy=0.6, average_dwell_hours=72,
            weather_available=True, weather_risk_factor=0.2,
            source_quality=0.8, freshness_state="available",
        )
        r1 = evaluate_congestion(sig)
        r2 = evaluate_congestion(sig)
        assert r1.score == r2.score
        assert r1.level == r2.level

    def test_bounded_score(self):
        from maritime.congestion.model import (
            CongestionSignals, evaluate_congestion, CongestionModelConfig,
        )
        sig = CongestionSignals(
            entity_type="port", latitude=10.0, longitude=10.0,
            observed_at=_ts(),
            traffic_density=1.0, cargo_density=1.0, tanker_density=1.0,
            passenger_density=1.0, traffic_change_ratio=10.0,
            port_call_count=1000, utilization_proxy=1.0, average_dwell_hours=1000,
            queue_proxy=1.0, arrival_rate_per_day=1000,
            weather_available=True, weather_risk_factor=1.0,
            source_quality=1.0, freshness_state="available",
        )
        r = evaluate_congestion(sig)
        assert 0.0 <= r.score <= 1.0

    def test_correct_level_classification(self):
        from maritime.congestion.model import (
            CongestionSignals, evaluate_congestion,
        )
        # All inputs at 1.0 — score must land in the severe band.
        full = CongestionSignals(
            entity_type="port", latitude=10.0, longitude=10.0,
            observed_at=_ts(),
            traffic_density=1.0, cargo_density=1.0, tanker_density=1.0,
            passenger_density=1.0, traffic_change_ratio=10.0,
            port_call_count=1000, utilization_proxy=1.0, average_dwell_hours=200,
            queue_proxy=1.0, arrival_rate_per_day=1000,
            weather_available=True, weather_risk_factor=1.0,
            source_quality=0.9, freshness_state="available",
        )
        assert evaluate_congestion(full).level == "severe"
        # Empty → low
        empty = CongestionSignals(
            entity_type="port", latitude=10.0, longitude=10.0,
            observed_at=_ts(), source_quality=0.5,
        )
        assert evaluate_congestion(empty).level == "low"

    def test_confidence_drops_with_missing(self):
        from maritime.congestion.model import (
            CongestionSignals, evaluate_congestion,
        )
        full = CongestionSignals(
            entity_type="port", latitude=10.0, longitude=10.0,
            observed_at=_ts(),
            traffic_density=0.5, cargo_density=0.5, tanker_density=0.5,
            port_call_count=20, utilization_proxy=0.5, average_dwell_hours=24,
            weather_available=True, weather_risk_factor=0.2,
            source_quality=0.8,
        )
        empty = CongestionSignals(
            entity_type="port", latitude=10.0, longitude=10.0,
            observed_at=_ts(),
            source_quality=0.8,
        )
        c_full = evaluate_congestion(full).confidence
        c_empty = evaluate_congestion(empty).confidence
        assert c_full > c_empty

    def test_missing_source_behavior(self):
        from maritime.congestion.model import (
            CongestionSignals, evaluate_congestion,
        )
        sig = CongestionSignals(
            entity_type="port", latitude=10.0, longitude=10.0,
            observed_at=_ts(),
            source_quality=0.5,
        )
        r = evaluate_congestion(sig)
        assert r.score == 0.0  # nothing to score on
        assert r.missing  # at least some missing inputs
        assert r.confidence < 1.0

    def test_fallback_weather_unavailable(self):
        from maritime.congestion.model import (
            CongestionSignals, evaluate_congestion,
        )
        sig = CongestionSignals(
            entity_type="port", latitude=10.0, longitude=10.0,
            observed_at=_ts(),
            traffic_density=0.5,
            port_call_count=20, utilization_proxy=0.5,
            weather_available=False, source_quality=0.8,
        )
        r = evaluate_congestion(sig)
        # weather_risk must be 0.0 and missing list must include weather
        assert r.components["weather_risk"] == 0.0
        assert "weather" in r.missing
        # Traffic + port_pressure should still contribute
        assert r.score > 0.0

    def test_explainability_output(self):
        from maritime.congestion.model import (
            CongestionSignals, evaluate_congestion,
        )
        sig = CongestionSignals(
            entity_type="port", latitude=10.0, longitude=10.0,
            observed_at=_ts(),
            traffic_density=0.5, cargo_density=0.3, tanker_density=0.2,
            port_call_count=20, utilization_proxy=0.6, average_dwell_hours=24,
            weather_available=True, weather_risk_factor=0.2,
            source_quality=0.8,
        )
        r = evaluate_congestion(sig)
        assert "traffic" in r.components
        assert "port_pressure" in r.components
        assert "weather_risk" in r.components
        assert "traffic_change" in r.components

    def test_stale_reduces_confidence(self):
        from maritime.congestion.model import (
            CongestionSignals, evaluate_congestion,
        )
        sig_available = CongestionSignals(
            entity_type="port", latitude=10.0, longitude=10.0,
            observed_at=_ts(),
            traffic_density=0.5,
            port_call_count=20, utilization_proxy=0.5,
            source_quality=0.8, freshness_state="available",
        )
        sig_stale = CongestionSignals(
            entity_type="port", latitude=10.0, longitude=10.0,
            observed_at=_ts(),
            traffic_density=0.5,
            port_call_count=20, utilization_proxy=0.5,
            source_quality=0.8, freshness_state="stale",
        )
        c_av = evaluate_congestion(sig_available).confidence
        c_st = evaluate_congestion(sig_stale).confidence
        assert c_st < c_av


# --------------------------------------------------------------------
# 3. Orchestrator tests
# --------------------------------------------------------------------


class TestCongestionOrchestrator:
    def setup_method(self):
        # Use an isolated snapshot root for each test.
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.snapshot_root = Path(self._tmp_ctx.name)

    def teardown_method(self):
        try:
            self._tmp_ctx.cleanup()
        except Exception:
            pass

    def test_default_disabled(self, monkeypatch):
        from maritime.congestion.orchestrator import (
            CongestionOrchestrator, CongestionOrchestratorConfig,
        )
        cfg = CongestionOrchestratorConfig(enabled=False)
        orch = CongestionOrchestrator(config=cfg, snapshot_root=self.snapshot_root)
        r = orch.run()
        assert r.ok is False
        assert r.error_kind == "disabled"

    def test_enabled_publishes_synthetic(self):
        from maritime.congestion.orchestrator import (
            CongestionOrchestrator, CongestionOrchestratorConfig,
        )
        cfg = CongestionOrchestratorConfig(enabled=True, synthetic_when_empty=True)
        orch = CongestionOrchestrator(config=cfg, snapshot_root=self.snapshot_root)
        r = orch.run()
        assert r.ok is True
        assert r.snapshot_path is not None
        assert Path(r.snapshot_path).exists()
        # Records file present
        recs_path = Path(r.snapshot_path)
        assert recs_path.name == "congestion_records.jsonl"
        with open(recs_path) as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        assert lines
        # All records are synthetic (no upstream data)
        for line in lines:
            rec = json.loads(line)
            assert rec["synthetic"] is True
        # At least one manifest file
        assert r.manifest_path is not None
        assert Path(r.manifest_path).exists()

    def test_telemetry_events(self):
        from maritime.congestion.orchestrator import (
            CongestionOrchestrator, CongestionOrchestratorConfig,
        )
        from maritime import telemetry
        telemetry.reset_events()
        cfg = CongestionOrchestratorConfig(enabled=True, synthetic_when_empty=True)
        orch = CongestionOrchestrator(config=cfg, snapshot_root=self.snapshot_root)
        orch.run()
        events = [e["event"] for e in telemetry.get_events()]
        assert "maritime_congestion_run_completed" in events

    def test_idempotent_double_run(self):
        from maritime.congestion.orchestrator import (
            CongestionOrchestrator, CongestionOrchestratorConfig,
        )
        cfg = CongestionOrchestratorConfig(enabled=True, synthetic_when_empty=True)
        orch = CongestionOrchestrator(config=cfg, snapshot_root=self.snapshot_root)
        r1 = orch.run()
        r2 = orch.run()
        assert r1.ok and r2.ok
        assert r1.snapshot_id != r2.snapshot_id  # unique IDs per run

    def test_inputs_missing_when_no_upstream(self):
        from maritime.congestion.orchestrator import (
            CongestionOrchestrator, CongestionOrchestratorConfig,
        )
        cfg = CongestionOrchestratorConfig(enabled=True, synthetic_when_empty=True)
        orch = CongestionOrchestrator(config=cfg, snapshot_root=self.snapshot_root)
        r = orch.run()
        # No upstream local snapshots, so all four inputs are missing
        for label in ("traffic", "port", "live", "weather"):
            assert label in r.inputs_missing
        assert r.synthetic is True

    def test_deterministic_synthetic_records(self):
        from maritime.congestion.orchestrator import (
            CongestionOrchestrator, CongestionOrchestratorConfig,
        )
        # Fix the computation timestamp to make the run reproducible.
        cfg = CongestionOrchestratorConfig(enabled=True, synthetic_when_empty=True)
        orch1 = CongestionOrchestrator(config=cfg, snapshot_root=self.snapshot_root)
        orch2 = CongestionOrchestrator(config=cfg, snapshot_root=self.snapshot_root)
        r1 = orch1.run()
        r2 = orch2.run()
        # Both should produce records with the same structure
        recs1 = [json.loads(l) for l in Path(r1.snapshot_path).read_text().splitlines() if l.strip()]
        recs2 = [json.loads(l) for l in Path(r2.snapshot_path).read_text().splitlines() if l.strip()]
        ids1 = sorted(r["entity_id"] for r in recs1)
        ids2 = sorted(r["entity_id"] for r in recs2)
        assert ids1 == ids2


# --------------------------------------------------------------------
# 4. FeatureAdapter tests
# --------------------------------------------------------------------


class TestCongestionFeatureAdapter:
    def setup_method(self):
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.snapshot_root = Path(self._tmp_ctx.name)
        # Produce a snapshot to read from.
        from maritime.congestion.orchestrator import (
            CongestionOrchestrator, CongestionOrchestratorConfig,
        )
        cfg = CongestionOrchestratorConfig(enabled=True, synthetic_when_empty=True)
        orch = CongestionOrchestrator(config=cfg, snapshot_root=self.snapshot_root)
        orch.run()

    def teardown_method(self):
        try:
            self._tmp_ctx.cleanup()
        except Exception:
            pass

    def test_latest_snapshot(self):
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter(
            store=None,
        )
        # Override the adapter's store base to point at the temp root
        adp._store._base = self.snapshot_root  # type: ignore[attr-defined]
        snap = adp.latest_snapshot()
        assert snap is not None
        assert snap.get("dataset_key") == "maritime_congestion"

    def test_source_status(self):
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter()
        adp._store._base = self.snapshot_root  # type: ignore[attr-defined]
        s = adp.source_status()
        assert s.ok is True
        assert s.snapshot_id is not None

    def test_congestion_at(self):
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter()
        adp._store._base = self.snapshot_root  # type: ignore[attr-defined]
        # Norfolk is one of the synthetic locations.
        r = adp.congestion_at(latitude=36.85, longitude=-76.29, radius_km=200.0, limit=4)
        assert r.records

    def test_congestion_for_port(self):
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter()
        adp._store._base = self.snapshot_root  # type: ignore[attr-defined]
        r = adp.congestion_for_port("norfolk")
        assert r.records

    def test_congestion_along_route(self):
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter()
        adp._store._base = self.snapshot_root  # type: ignore[attr-defined]
        r = adp.congestion_along_route(
            waypoints=[(53.55, 9.99), (36.85, -76.29)],
            radius_km=200.0,
        )
        assert r.records

    def test_high_congestion_regions(self):
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter()
        adp._store._base = self.snapshot_root  # type: ignore[attr-defined]
        r = adp.high_congestion_regions(threshold=0.0, limit=10)
        # All synthetic records should be returned
        assert r.records

    def test_congestion_summary(self):
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        adp = CongestionFeatureAdapter()
        adp._store._base = self.snapshot_root  # type: ignore[attr-defined]
        s = adp.congestion_summary()
        assert s.records
        summary = s.records[0]
        assert "by_level" in summary
        assert "entity_count" in summary

    def test_no_network_imports_in_congestion_package(self):
        # The congestion package must not open sockets or call urllib.
        forbidden = {"urllib", "socket", "httpx", "aiohttp", "requests"}
        import ast
        pkg = REPO_ROOT / "maritime" / "congestion"
        for path in sorted(pkg.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name.split(".")[0] not in forbidden, (
                            f"{path.relative_to(REPO_ROOT)} imports forbidden {alias.name}"
                        )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module.split(".")[0] not in forbidden, (
                        f"{path.relative_to(REPO_ROOT)} imports forbidden {node.module}"
                    )

    def test_empty_snapshot_safe(self):
        from maritime.congestion.feature_adapter import CongestionFeatureAdapter
        with tempfile.TemporaryDirectory() as tmp:
            empty_root = Path(tmp)
            adp = CongestionFeatureAdapter()
            adp._store._base = empty_root  # type: ignore[attr-defined]
            r = adp.congestion_at(latitude=0.0, longitude=0.0)
            assert r.ok is False
            assert r.error is not None


# --------------------------------------------------------------------
# 5. Feature-flag tests
# --------------------------------------------------------------------


class TestFeatureFlags:
    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("MARITIME_CONGESTION_ENABLED", raising=False)
        from maritime.congestion.orchestrator import (
            CongestionOrchestratorConfig,
        )
        cfg = CongestionOrchestratorConfig.from_env()
        assert cfg.enabled is False

    def test_explicit_on(self, monkeypatch):
        monkeypatch.setenv("MARITIME_CONGESTION_ENABLED", "1")
        from maritime.congestion.orchestrator import (
            CongestionOrchestratorConfig,
        )
        cfg = CongestionOrchestratorConfig.from_env()
        assert cfg.enabled is True

    def test_weights_overridable(self, monkeypatch):
        monkeypatch.setenv("MARITIME_CONGESTION_TRAFFIC_WEIGHT", "0.7")
        monkeypatch.setenv("MARITIME_CONGESTION_PORT_WEIGHT", "0.1")
        monkeypatch.setenv("MARITIME_CONGESTION_WEATHER_WEIGHT", "0.1")
        from maritime.congestion.model import CongestionModelConfig
        cfg = CongestionModelConfig.from_env()
        assert cfg.traffic_weight == 0.7


# --------------------------------------------------------------------
# 6. Network isolation & optimizer guard
# --------------------------------------------------------------------


class TestNetworkIsolation:
    def test_congestion_no_urllib_or_socket(self):
        # Re-check at runtime that no module under maritime.congestion
        # imported the forbidden stdlib network helpers.
        for name in ("urllib", "socket"):
            assert name not in dir(__import__("maritime.congestion.model", fromlist=["*"]))
            assert name not in dir(__import__("maritime.congestion.orchestrator", fromlist=["*"]))
            assert name not in dir(__import__("maritime.congestion.feature_adapter", fromlist=["*"]))

    def test_optimizer_does_not_import_congestion(self):
        # The optimizer source tree must not import the congestion
        # layer. Phase 6 stops at the intelligence foundation.
        import ast
        src_root = REPO_ROOT / "src"
        offenders = []
        for path in src_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "congestion" in text.lower():
                # Allow comments / unrelated words; restrict to imports.
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if "congestion" in alias.name.lower():
                                offenders.append(str(path.relative_to(REPO_ROOT)))
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        if "congestion" in node.module.lower():
                            offenders.append(str(path.relative_to(REPO_ROOT)))
        assert not offenders, (
            "Optimizer must not import the congestion layer: " + ", ".join(offenders)
        )


# --------------------------------------------------------------------
# 7. Golden regression
# --------------------------------------------------------------------

class TestGoldenRegression:
    ARTIFACT = REPO_ROOT / "pipeline_output.json"
    BASELINE_SHA = "ad33a96e4e1d55332b1610d8a82b5a40f33246ce44d8182112930e3252a79e25"

    def test_pipeline_output_unchanged(self):
        if not self.ARTIFACT.exists():
            pytest.skip(f"{self.ARTIFACT} not present; skipping regression")
        actual = hashlib.sha256(self.ARTIFACT.read_bytes()).hexdigest()
        assert actual == self.BASELINE_SHA, (
            f"pipeline_output.json SHA-256 drifted: {actual} != {self.BASELINE_SHA}"
        )
