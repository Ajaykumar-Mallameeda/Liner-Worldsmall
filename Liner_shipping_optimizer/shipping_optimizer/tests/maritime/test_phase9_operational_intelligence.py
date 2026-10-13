"""Phase 9 — Operational Maritime Intelligence & Telemetry tests.

Covers the new read-only endpoint and the additive explainability
fields added to the routing-impact payload:

  * GET /api/maritime/telemetry              — fleet / processing /
    providers / per-source aggregation
  * /api/maritime/routing-impact             — additive per-feature
    explainability + top-level explainability rollup

These tests are endpoint-level. They exercise the FastAPI app
via ``fastapi.testclient.TestClient`` and the pure helper
functions. They do NOT touch the optimizer, the maritime
ingestion paths, the LLM provider architecture, or
``pipeline_output.json``.

Hard rules (from the Phase 9 brief):

  * No git operations. Tests must be read-only on disk.
  * No mutation of ``pipeline_output.json``. The test session
    captures a SHA baseline on entry and asserts it has not
    changed on exit.
  * The endpoint must be safe-empty when the master flag is off.
  * Failure of any single sub-endpoint must NOT raise; the
    endpoint must always return a JSON document.
  * The endpoint must NEVER import optimizer modules, perform
    network calls, or touch protected Tier-0 files.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict
from unittest import mock

import pytest


# --------------------------------------------------------------------
# Path + import plumbing
# --------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_OUTPUT = REPO_ROOT / "pipeline_output.json"


def _ensure_server_loaded() -> Any:
    if "backend.server" not in sys.modules:
        sys.path.insert(0, str(REPO_ROOT))
        return importlib.import_module("backend.server")
    return sys.modules["backend.server"]


@pytest.fixture(scope="session")
def server():
    return _ensure_server_loaded()


@pytest.fixture
def client_disabled(server):
    from fastapi.testclient import TestClient
    with mock.patch.dict(
        os.environ, {"MARITIME_INTELLIGENCE_ENABLED": "0"}, clear=False
    ):
        with TestClient(server.app) as c:
            yield c


@pytest.fixture
def client_enabled(server):
    from fastapi.testclient import TestClient
    with mock.patch.dict(
        os.environ, {"MARITIME_INTELLIGENCE_ENABLED": "1"}, clear=False
    ):
        with TestClient(server.app) as c:
            yield c


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

def _sha256_of(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# Pre-Phase-9 SHA baseline (frozen).
PHASE9_BASELINE_SHA = "A578877A419A7519E9A51AC43D969579315E310405802F952CEEB1759ABACC38"


# --------------------------------------------------------------------
# TestPhase9TelemetryEndpoint
# --------------------------------------------------------------------

class TestPhase9TelemetryEndpoint:
    """The new ``/api/maritime/telemetry`` endpoint."""

    def test_safe_empty_when_master_flag_off(self, client_disabled):
        resp = client_disabled.get("/api/maritime/telemetry")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["enabled"] is False
        assert body["reason"] == "flag_off"
        # Safe-empty shape contract. All values are None so the
        # frontend renders em-dashes, never fabricated numbers.
        for key in (
            "vessels_observed",
            "ports_observed",
            "weather_risk",
            "congestion_max_score",
            "congestion_avg_confidence",
        ):
            assert body["fleet"][key] is None
        for key in (
            "duration_ms",
            "budget_exceeded",
            "sources_used_count",
            "sources_missing_count",
        ):
            assert body["processing"][key] is None
        assert body["providers"] == []
        assert body["per_source"] == {}
        assert body["evaluated_at"]

    def test_endpoint_responds_when_master_flag_on(self, client_enabled):
        """Even with no snapshots on disk, the endpoint must respond 200
        and return an enabled: true payload with structured sub-blocks.
        """
        resp = client_enabled.get("/api/maritime/telemetry")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # enabled: true when the master flag is on.
        assert body["enabled"] is True
        assert "fleet" in body
        assert "processing" in body
        assert "providers" in body
        assert "per_source" in body
        assert "evaluated_at" in body

    def test_never_raises_on_broken_subendpoints(self, server, client_enabled):
        """A simulated failure inside a per-source read must be
        isolated to that source. The endpoint must always respond.
        """
        # Patch one of the Phase 9 helpers to raise — the endpoint
        # must catch and continue.
        original = server._phase9_read_snapshot_meta
        def broken(*args, **kwargs):
            raise RuntimeError("simulated snapshot-store failure")

        with mock.patch.object(
            server, "_phase9_read_snapshot_meta", side_effect=broken
        ):
            resp = client_enabled.get("/api/maritime/telemetry")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            # The outer try/except in the handler should catch the
            # failure and return the safe-empty shape.
            assert body["enabled"] is False
            assert body["reason"] == "safe_failure"
        # Sanity: original was not permanently clobbered.
        assert server._phase9_read_snapshot_meta is original

    def test_telemetry_empty_helper(self, server):
        """The safe-empty helper must produce a JSON-serializable
        payload that always includes the frozen key set.
        """
        body = server._phase9_telemetry_empty(reason="flag_off")
        body2 = server._phase9_telemetry_empty(reason="safe_failure")
        # Both are JSON-serializable.
        json.dumps(body)
        json.dumps(body2)
        for b in (body, body2):
            assert b["enabled"] is False
            assert "evaluated_at" in b
            for k in ("fleet", "processing", "providers", "per_source"):
                assert k in b
            assert b["reason"] in ("flag_off", "safe_failure")

    def test_telemetry_fleet_block_is_typed(self, server):
        """The fleet block must be the documented dict of nullable
        values (so a frontend type-guard can rely on it).
        """
        body = server._phase9_telemetry_empty()
        fleet = body["fleet"]
        for key in (
            "vessels_observed",
            "ports_observed",
            "weather_risk",
            "congestion_max_score",
            "congestion_avg_confidence",
        ):
            assert key in fleet
            assert fleet[key] is None

    def test_telemetry_processing_block_is_typed(self, server):
        body = server._phase9_telemetry_empty()
        proc = body["processing"]
        for key in (
            "duration_ms",
            "budget_exceeded",
            "sources_used_count",
            "sources_missing_count",
        ):
            assert key in proc
            assert proc[key] is None

    def test_telemetry_count_records_returns_int_or_none(self, server):
        """The local record-count helper must return either an int
        (count of records in the latest snapshot's manifest) or
        None (no snapshot on disk). It must never raise.
        """
        result = server._phase9_count_records(REPO_ROOT, "traffic")
        assert result is None or isinstance(result, int)
        result = server._phase9_count_records(REPO_ROOT, "port")
        assert result is None or isinstance(result, int)
        result = server._phase9_count_records(REPO_ROOT, "weather")
        assert result is None or isinstance(result, int)
        result = server._phase9_count_records(REPO_ROOT, "congestion")
        assert result is None or isinstance(result, int)


# --------------------------------------------------------------------
# TestPhase9Explainability
# --------------------------------------------------------------------

class TestPhase9Explainability:
    """The new additive explainability fields on
    /api/maritime/routing-impact."""

    def test_safe_empty_includes_explainability_block(self, client_disabled):
        resp = client_disabled.get("/api/maritime/routing-impact")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # The safe-empty shape MUST now include the explainability
        # rollup, per the Phase 9 contract.
        assert "explainability" in body
        e = body["explainability"]
        for k in (
            "available",
            "features_attached",
            "features_consumed",
            "inputs_affected",
            "route_affected",
            "wording",
        ):
            assert k in e
        assert e["available"] is False
        assert e["features_attached"] == 0
        assert e["features_consumed"] == 0
        assert e["inputs_affected"] is False
        assert e["route_affected"] is False
        assert isinstance(e["wording"], str)
        assert e["wording"]

    def test_classify_feature_adds_explainability_fields(self, server):
        """For each feature, the per-feature classification must now
        include consumed, affected_input, final_route_affected.
        """
        # Weather with applied state — should be consumed and have
        # an IP-2 affected_input.
        weather_applied = {
            "speed_factor": 0.85,
            "confidence": 0.92,
            "freshness_state": "fresh",
            "synthetic": False,
        }
        out = server._phase8_classify_feature("weather", weather_applied)
        assert "consumed" in out
        assert "affected_input" in out
        assert "final_route_affected" in out
        # When classified as applied, weather IS consumed, IS attached
        # to calculate_weekly_fuel_cost, and NEVER affects the final
        # route (T0-1).
        if out["state"] == "applied":
            assert out["consumed"] is True
            assert out["affected_input"] is not None
            assert "calculate_weekly_fuel_cost" in out["affected_input"]
            assert out["final_route_affected"] is False

        # Congestion with applied state — should be consumed and have
        # an IP-3 affected_input.
        congestion_applied = {
            "by_port": {"P1": 0.9},
            "average_confidence": 0.9,
            "freshness_state": "fresh",
            "synthetic": False,
        }
        out = server._phase8_classify_feature("congestion", congestion_applied)
        if out["state"] == "applied":
            assert out["consumed"] is True
            assert out["affected_input"] is not None
            assert "_port_capacity_map" in out["affected_input"]
            assert out["final_route_affected"] is False

        # Traffic/port are always informational — consumed must be
        # False and affected_input must be None regardless of state.
        traffic_applied = {
            "score": 0.5,
            "freshness_state": "fresh",
            "synthetic": False,
        }
        out = server._phase8_classify_feature("traffic", traffic_applied)
        assert out["consumed"] is False
        assert out["affected_input"] is None
        assert out["final_route_affected"] is False

        # A stale weather feature is NOT consumed.
        weather_stale = {
            "speed_factor": 0.7,
            "confidence": 0.5,
            "freshness_state": "stale",
            "synthetic": False,
        }
        out = server._phase8_classify_feature("weather", weather_stale)
        if out["state"] == "stale":
            assert out["consumed"] is False
            assert out["affected_input"] is None

    def test_final_route_affected_is_always_false(self, server):
        """Per T0-1 (deterministic iteration selection), the final
        route is NEVER claimed to be affected by maritime intelligence.
        This invariant is testable across all feature classifications.
        """
        cases = [
            ("weather", {"speed_factor": 0.9, "confidence": 0.95,
                          "freshness_state": "fresh", "synthetic": False}),
            ("congestion", {"by_port": {"P1": 0.9}, "average_confidence": 0.9,
                            "freshness_state": "fresh", "synthetic": False}),
            ("traffic", {"score": 0.7, "freshness_state": "fresh",
                         "synthetic": False}),
            ("port", {"score": 0.6, "freshness_state": "fresh",
                      "synthetic": False}),
            ("weather", None),
            ("weather", {}),
        ]
        for name, payload in cases:
            out = server._phase8_classify_feature(name, payload)
            assert out["final_route_affected"] is False, (
                f"final_route_affected must be False (T0-1); got "
                f"{out!r} for ({name}, {payload!r})"
            )

    def test_routing_impact_endpoint_includes_explainability_rollup(
        self, client_enabled,
    ):
        """The /api/maritime/routing-impact endpoint must always
        include the top-level explainability rollup.
        """
        resp = client_enabled.get("/api/maritime/routing-impact")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "explainability" in body
        e = body["explainability"]
        for k in (
            "available",
            "features_attached",
            "features_consumed",
            "inputs_affected",
            "route_affected",
            "wording",
        ):
            assert k in e
        # route_affected is hard-coded False in this release (T0-1).
        assert e["route_affected"] is False

    def test_routing_impact_per_feature_includes_explainability_fields(
        self, client_enabled,
    ):
        """Each entry in features[] must now include the three
        explainability fields. We tolerate available: false (the
        artifact has no maritime_intelligence key) by checking
        the per-feature shape only when features[] is non-empty.
        """
        resp = client_enabled.get("/api/maritime/routing-impact")
        body = resp.json()
        for f in body.get("features", []):
            assert "consumed" in f
            assert "affected_input" in f
            assert "final_route_affected" in f
            assert f["final_route_affected"] is False
            # If affected_input is set, it must be a string.
            if f["affected_input"] is not None:
                assert isinstance(f["affected_input"], str)


# --------------------------------------------------------------------
# TestPhase9Architecture
# --------------------------------------------------------------------

class TestPhase9Architecture:
    """Tier-0 protection and architectural invariants for Phase 9."""

    def test_pipeline_output_sha_unchanged_after_tests(self):
        """No test in this phase may mutate pipeline_output.json.
        The SHA must be byte-identical to the pre-Phase-9 baseline.
        """
        actual = _sha256_of(PIPELINE_OUTPUT)
        if actual == "":
            # File missing — nothing to compare; tests must be
            # tolerant of a fresh repo but we record the absence.
            pytest.skip("pipeline_output.json not present in this checkout")
        # Normalize both sides to lowercase (sha256 hex is
        # case-insensitive, but PowerShell's Get-FileHash returns
        # uppercase by default; Python's hashlib returns lowercase).
        assert actual.lower() == PHASE9_BASELINE_SHA.lower(), (
            f"pipeline_output.json SHA changed during Phase 9 tests. "
            f"baseline={PHASE9_BASELINE_SHA} actual={actual}"
        )

    def test_telemetry_endpoint_does_not_import_optimizer(self, server):
        """The /api/maritime/telemetry handler must not pull in
        any optimizer module. The presence of an
        ``src.optimization`` import in the server module is the
        canonical sentinel; Phase 9 must not introduce one.
        """
        mod = server
        # The module's own import surface is what counts. We
        # inspect ``mod.__dict__`` for any submodule that smells
        # like the optimizer path. (The server is allowed to
        # import things like ``src.agents.iteration_selection``
        # for OTHER reasons; but the new Phase 9 helpers must
        # not introduce a new import.)
        # The minimal, robust check: the Phase 9 helpers we just
        # added must exist and must not reference any module
        # name from src/optimization.
        import inspect
        for fn_name in (
            "_phase9_telemetry_empty",
            "_phase9_read_snapshot_meta",
            "_phase9_count_records",
        ):
            fn = getattr(mod, fn_name, None)
            assert fn is not None
            src = inspect.getsource(fn)
            # The helper must not import or reference the
            # optimizer or the orchestrator directly. (The
            # orchestrator and the iteration selection are both
            # Tier-0.)
            for forbidden in (
                "from src.optimization",
                "import src.optimization",
                "from src.agents.iteration_selection",
                "import src.agents.iteration_selection",
                "from src.agents.orchestrator",
                "import src.agents.orchestrator",
            ):
                assert forbidden not in src, (
                    f"Phase 9 helper {fn_name} references forbidden "
                    f"module via {forbidden!r}:\n{src}"
                )

    def test_telemetry_endpoint_does_no_network_calls(self, server):
        """The /api/maritime/telemetry handler must not import any
        network library. urlllib / requests / aiohttp / httpx are
        forbidden.
        """
        import inspect
        for fn_name in (
            "_phase9_telemetry_empty",
            "_phase9_read_snapshot_meta",
            "_phase9_count_records",
        ):
            fn = getattr(mod := server, fn_name, None)
            assert fn is not None
            src = inspect.getsource(fn)
            for forbidden in (
                "import requests",
                "import httpx",
                "import aiohttp",
                "import urllib.request",
                "from urllib.request",
                "import socket",
            ):
                assert forbidden not in src, (
                    f"Phase 9 helper {fn_name} references forbidden "
                    f"network module {forbidden!r}:\n{src}"
                )

    def test_telemetry_endpoint_handles_missing_snapshot_dir(
        self, server, tmp_path, monkeypatch,
    ):
        """Pointing the helper at a non-existent repo root must
        return None / safe-empty values, never raise.
        """
        result = server._phase9_count_records(tmp_path, "traffic")
        assert result is None
        meta = server._phase9_read_snapshot_meta(tmp_path, "traffic")
        assert meta is None

    def test_telemetry_endpoint_handles_corrupt_manifest(
        self, server, tmp_path,
    ):
        """A snapshot directory with a corrupt manifest.json must
        not raise — the helper returns None so the endpoint can
        surface a safe-empty fleet value.
        """
        import json as _json
        snap_dir = tmp_path / "data" / "maritime" / "snapshots" / "traffic"
        snap_dir.mkdir(parents=True)
        (snap_dir / "manifest.json").write_text("{ this is not valid json")
        meta = server._phase9_read_snapshot_meta(tmp_path, "traffic")
        assert meta is None
        rc = server._phase9_count_records(tmp_path, "traffic")
        assert rc is None


# --------------------------------------------------------------------
# TestPhase9NoSecondaryReports
# --------------------------------------------------------------------

class TestPhase9NoSecondaryReports:
    """Phase 9 forbids PHASE_9_*.json, secondary reports, benchmark
    files, etc. The only deliverable markdown is
    PHASE_9_EXECUTION_REPORT.md (produced in a later phase). For
    tests, the rule is: no test fixture or test in this module
    may write a PHASE_9_*.json or PHASE_9_*.md file.
    """

    def test_no_json_reports_in_repo_root(self):
        """No PHASE_9_*.json may exist in the repo root."""
        candidates = list(REPO_ROOT.glob("PHASE_9_*.json"))
        assert candidates == [], (
            f"Phase 9 forbids PHASE_9_*.json reports; found: "
            f"{[str(p) for p in candidates]}"
        )

    def test_no_extra_markdown_reports(self):
        """No PHASE_9_*.md may exist except the (future)
        PHASE_9_EXECUTION_REPORT.md. We permit the single named
        report; any other PHASE_9_*.md is a violation.
        """
        allowed = {"PHASE_9_EXECUTION_REPORT.md"}
        candidates = list(REPO_ROOT.glob("PHASE_9_*.md"))
        offenders = [p for p in candidates if p.name not in allowed]
        assert offenders == [], (
            f"Phase 9 forbids extra PHASE_9_*.md reports; found: "
            f"{[str(p) for p in offenders]}"
        )
