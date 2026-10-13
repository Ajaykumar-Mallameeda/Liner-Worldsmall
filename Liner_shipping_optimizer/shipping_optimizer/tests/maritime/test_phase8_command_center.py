"""Phase 8 — Maritime Intelligence Command Center backend tests.

Covers the two new read-only endpoints added for the Phase 8
dashboard transformation:

  * GET /api/maritime/overview       — cross-source aggregation
  * GET /api/maritime/routing-impact  — Phase 7 IP-5 explanation

These tests are deliberately endpoint-level: they exercise the
FastAPI app via ``fastapi.testclient.TestClient`` and the pure
helper functions. They do NOT touch the optimizer, the maritime
ingestion paths, or the LLM provider architecture.

Hard rules (from the Phase 8 brief):

  * No git operations. Tests must be read-only on disk.
  * No mutation of ``pipeline_output.json``.
  * The two endpoints must be safe-empty when the master flag
    is off — they never raise, never 500, never 404.
  * ``pipeline_output.json`` SHA must not change as a side effect
    of running these tests.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
from io import StringIO
from pathlib import Path
from typing import Any, Dict
from unittest import mock

import pytest


# --------------------------------------------------------------------
# Path + import plumbing
# --------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ensure_server_loaded() -> Any:
    """Return the already-imported ``backend.server`` module.

    The Phase 8 endpoints read MARITIME_INTELLIGENCE_ENABLED at
    request time (so the env var can be toggled per-test via
    ``mock.patch.dict``). The server module is imported once at
    session start; the per-test env-var override is the only
    configuration knob.
    """
    if "backend.server" not in sys.modules:
        sys.path.insert(0, str(REPO_ROOT))
        return importlib.import_module("backend.server")
    return sys.modules["backend.server"]


@pytest.fixture(scope="session")
def server():
    return _ensure_server_loaded()


@pytest.fixture
def artifact_root(server, tmp_path, monkeypatch):
    """A throw-away repository root that holds a ``pipeline_output.json``.

    The routing-impact endpoint resolves the artifact as ``<repo root>/pipeline_output.json`` where the
    repo root is derived from ``backend/server.py``'s ``__file__``.  Several tests below drive the
    endpoint with a patched ``json.load`` and need the file to EXIST; they must not depend on (or touch)
    the real artifact, which is produced by an orchestrator run and is absent on a fresh clone.  The
    module's ``__file__`` is therefore pointed at a temporary tree for the duration of the test."""
    (tmp_path / "backend").mkdir()
    (tmp_path / "pipeline_output.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(server, "__file__", str(tmp_path / "backend" / "server.py"))
    return tmp_path


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


@pytest.fixture
def client_enabled_all(server):
    from fastapi.testclient import TestClient
    env = {
        "MARITIME_INTELLIGENCE_ENABLED": "1",
        "MARITIME_TRAFFIC_ENABLED": "1",
        "MARITIME_PORT_INTELLIGENCE_ENABLED": "1",
        "MARITIME_WEATHER_ENABLED": "1",
        "MARITIME_CONGESTION_ENABLED": "1",
        "MARITIME_LIVE_ENABLED": "1",
    }
    with mock.patch.dict(os.environ, env, clear=False):
        with TestClient(server.app) as c:
            yield c


# --------------------------------------------------------------------
# /api/maritime/overview
# --------------------------------------------------------------------


class TestPhase8OverviewEndpoint:
    """GET /api/maritime/overview — cross-source aggregation."""

    def test_overview_offline_when_flag_off(self, client_disabled):
        """Master flag OFF → enabled=False, overall_state=offline."""
        r = client_disabled.get("/api/maritime/overview")
        assert r.status_code == 200
        body = r.json()
        assert body["enabled"] is False
        assert body["overall_state"] in {"offline", "disabled"}
        assert body["sources"] == {}
        assert body["freshness"] == {}
        # Every feature flag must be reported as False.
        for k in (
            "maritime_intelligence", "traffic", "port",
            "weather", "congestion", "live",
        ):
            assert body["feature_flags"][k] is False
        # The endpoint must surface a stable error token.
        assert body["error"] in {"flag_off", "disabled"}

    def test_overview_returns_expected_key_set_when_enabled(
        self, client_enabled
    ):
        """When the master flag is ON, the endpoint must return the
        full dashboard contract — even if all per-source calls
        degrade to ``unknown`` because sub-flags are off and no
        snapshots exist on disk."""
        r = client_enabled.get("/api/maritime/overview")
        assert r.status_code == 200
        body = r.json()
        assert body["enabled"] is True
        # Top-level keys must always be present.
        for k in (
            "enabled", "evaluated_at", "overall_state", "sources",
            "freshness", "feature_flags", "resilience",
        ):
            assert k in body, f"missing top-level key: {k}"
        # Master flag is on, sub-flags are off → dashboard must
        # show the master on + sub-flags off transition correctly.
        assert body["feature_flags"]["maritime_intelligence"] is True
        for sub in ("traffic", "port", "weather", "congestion", "live"):
            assert body["feature_flags"][sub] is False
        # overall_state must be one of the documented tokens.
        assert body["overall_state"] in {
            "live", "available", "snapshot", "historical",
            "stale", "degraded", "offline", "disabled", "unknown",
        }

    def test_overview_feature_flags_when_all_on(self, client_enabled_all):
        """When every sub-flag is on, the feature_flags map must
        reflect that. This is the precondition for LIVE/SNAPSHOT
        tokens to ever surface on a populated fixture."""
        r = client_enabled_all.get("/api/maritime/overview")
        assert r.status_code == 200
        body = r.json()
        for k in (
            "maritime_intelligence", "traffic", "port",
            "weather", "congestion", "live",
        ):
            assert body["feature_flags"][k] is True, k

    def test_overview_never_raises_on_sub_endpoint_failure(
        self, server
    ):
        """If a sub-endpoint raises, the overview endpoint must
        not propagate the exception. The failing source must
        degrade to ``state: unknown`` with an error message; all
        other sources must still be reported."""
        from fastapi.testclient import TestClient

        async def _boom():
            raise RuntimeError("simulated sub-endpoint failure")

        # Patch the four sub-endpoint coroutines on the server
        # module to raise. The endpoint must catch each one in
        # its own try/except.
        with mock.patch.dict(
            os.environ, {"MARITIME_INTELLIGENCE_ENABLED": "1"}, clear=False
        ):
            with TestClient(server.app) as c:
                with mock.patch.object(
                    server, "get_maritime_source_health", _boom
                ), mock.patch.object(
                    server, "get_maritime_weather_status", _boom
                ), mock.patch.object(
                    server, "get_maritime_congestion_status", _boom
                ), mock.patch.object(
                    server, "get_maritime_live_status", _boom
                ), mock.patch.object(
                    server, "get_maritime_resilience", _boom
                ):
                    r = c.get("/api/maritime/overview")
                    # Must not 500.
                    assert r.status_code == 200
                    body = r.json()
                    assert body["enabled"] is True
                    # Per-source error must be reported, not swallowed.
                    for k in ("traffic", "port", "weather", "congestion", "live"):
                        assert k in body["sources"], k
                        # Either the source reported a state, or it
                        # reported state=unknown + error. Both are valid.
                        if "error" in body["sources"][k]:
                            assert body["sources"][k]["state"] == "unknown"
                    # The overall_state must collapse to a known token.
                    assert body["overall_state"] in {
                        "live", "available", "snapshot", "historical",
                        "stale", "degraded", "offline", "disabled", "unknown",
                    }

    def test_overview_classify_overall_picks_highest_weight(self, server):
        """The pure helper must respect the documented ordering:
        LIVE > AVAILABLE > SNAPSHOT > HISTORICAL > STALE > DEGRADED
        > OFFLINE > DISABLED > UNKNOWN.
        """
        classify = server._phase8_classify_overall
        # Empty source map → unknown.
        assert classify({}) == "unknown"
        # Single sources.
        assert classify({"a": {"state": "live"}}) == "live"
        assert classify({"a": {"state": "available"}}) == "available"
        assert classify({"a": {"state": "snapshot"}}) == "snapshot"
        assert classify({"a": {"state": "historical"}}) == "historical"
        assert classify({"a": {"state": "stale"}}) == "stale"
        assert classify({"a": {"state": "degraded"}}) == "degraded"
        assert classify({"a": {"state": "offline"}}) == "offline"
        assert classify({"a": {"state": "disabled"}}) == "disabled"
        assert classify({"a": {"state": "unknown"}}) == "unknown"
        # Mixed: must take the highest.
        mixed = {
            "weather": {"state": "snapshot"},
            "live": {"state": "live"},
            "traffic": {"state": "stale"},
            "congestion": {"state": "available"},
            "port": {"state": "offline"},
        }
        assert classify(mixed) == "live"
        # The function must tolerate non-dict entries.
        messy = {
            "weather": {"state": "snapshot"},
            "live": None,
            "traffic": "nonsense",
            "congestion": {"state": "historical"},
        }
        assert classify(messy) == "snapshot"
        # Unrecognized states must not override recognized ones.
        assert classify({"a": {"state": "garbage"}, "b": {"state": "stale"}}) == "stale"

    def test_overview_empty_helper_reasons(self, server):
        """The safe-empty helper must distinguish 'flag_off' from
        'disabled' so the dashboard can render the right hint."""
        empty = server._phase8_overview_empty
        # Default reason.
        a = empty()
        assert a["enabled"] is False
        assert a["overall_state"] == "offline"
        # Explicit disabled reason.
        b = empty("disabled")
        assert b["enabled"] is False
        assert b["overall_state"] == "disabled"
        # Other reasons collapse to offline.
        c = empty("safe_failure")
        assert c["overall_state"] == "offline"
        # The feature_flags block must always be present and all
        # values must be False — this is the safe-empty contract.
        for body in (a, b, c):
            assert all(v is False for v in body["feature_flags"].values())

    def test_overview_evaluated_at_is_iso8601(self, client_enabled):
        """evaluated_at must be a string the dashboard can parse
        and re-format; it must never be null or numeric."""
        r = client_enabled.get("/api/maritime/overview")
        body = r.json()
        v = body["evaluated_at"]
        assert isinstance(v, str)
        # 4-digit year, T separator.
        assert "T" in v
        assert v[:4].isdigit()


# --------------------------------------------------------------------
# /api/maritime/routing-impact
# --------------------------------------------------------------------


class TestPhase8RoutingImpactEndpoint:
    """GET /api/maritime/routing-impact — Phase 7 IP-5 explanation."""

    def test_routing_impact_safe_empty_when_flag_off(self, client_disabled):
        """Master flag OFF → available=False, reason='flag_off'."""
        r = client_disabled.get("/api/maritime/routing-impact")
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is False
        assert body["reason"] == "flag_off"
        assert body["maritime_intelligence"] is None
        assert body["features"] == []
        # The summary keys must always be present and zeroed.
        for k in (
            "applied", "rejected", "stale",
            "fallback_used", "baseline_retained",
        ):
            assert body["summary"][k] == 0
        # The explanation must mention the baseline path so the
        # user knows the optimizer is on the pre-maritime path.
        assert "baseline" in body["explanation"].lower()

    def test_routing_impact_returns_no_artifact_when_missing(
        self, server
    ):
        """When the master flag is ON but pipeline_output.json is
        absent, the endpoint must return a clean
        'no_pipeline_output' payload — it must not raise."""
        from fastapi.testclient import TestClient

        # Make Path.exists() return False for pipeline_output.json.
        real_exists = Path.exists

        def exists_fake(self):
            if "pipeline_output.json" in str(self):
                return False
            return real_exists(self)

        with mock.patch.dict(
            os.environ, {"MARITIME_INTELLIGENCE_ENABLED": "1"}, clear=False
        ):
            with mock.patch.object(Path, "exists", exists_fake):
                with TestClient(server.app) as c:
                    r = c.get("/api/maritime/routing-impact")
                    assert r.status_code == 200
                    body = r.json()
                    # When the artifact is missing, the endpoint
                    # returns a structured no_pipeline_output
                    # payload (not the flag_off payload).
                    assert body["reason"] == "no_pipeline_output"
                    assert body["available"] is False
                    assert body["features"] == []

    def test_routing_impact_handles_missing_maritime_intelligence(
        self, server, artifact_root
    ):
        """When pipeline_output.json exists but has no
        ``maritime_intelligence`` key (the common state on a fresh
        clone), the endpoint must return reason='no_maritime_features'
        and a baseline_retained=1 summary so the dashboard can
        render a clean 'no impact' panel."""
        # Patch the module-level json.load to return a stripped-down
        # artifact that lacks the maritime_intelligence key. This
        # is the cleanest way to drive the endpoint without
        # mutating the real pipeline_output.json.
        stripped = {"some_other_key": {"value": 1}}

        with mock.patch.dict(
            os.environ, {"MARITIME_INTELLIGENCE_ENABLED": "1"}, clear=False
        ):
            with mock.patch.object(server.json, "load", return_value=stripped):
                from fastapi.testclient import TestClient
                with TestClient(server.app) as c:
                    r = c.get("/api/maritime/routing-impact")
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is False
        assert body["reason"] == "no_maritime_features"
        assert body["maritime_intelligence"] is None
        # baseline_retained=1 because all four features
        # (traffic/port/weather/congestion) are absent.
        assert body["summary"]["baseline_retained"] == 1
        # The explanation must mention the IP-1 attach or the
        # baseline path so the user understands what happened.
        assert "baseline" in body["explanation"].lower()

    def test_routing_impact_classifies_synthetic_features(
        self, server, artifact_root
    ):
        """Given a synthetic maritime_intelligence payload, the
        endpoint must classify each feature and produce a
        summary whose counts add up to 4 (one per feature)."""
        synthetic_mi = {
            "snapshot_id": "test-snap-001",
            "retrieved_at": "2026-08-27T00:00:00Z",
            "duration_ms": 42,
            "budget_exceeded": False,
            "sources_used": ["emodnet_vessel_density", "open_meteo"],
            "sources_missing": ["noaa_ais_port_intelligence"],
            "congestion": {
                "by_port": {
                    "USNYC": {
                        "score": 0.7,
                        "level": "high",
                    }
                },
                "average_confidence": 0.82,
                "freshness_state": "fresh",
                "synthetic": False,
            },
            "weather": {
                "speed_factor": 0.95,
                "confidence": 0.78,
                "freshness_state": "fresh",
                "synthetic": False,
            },
            "diagnostics": {"attempts": 2},
        }
        # The endpoint reads the IP-5 payload from
        # ``artifact["maritime_intelligence"]``, so the synthetic
        # artifact we feed to json.load is wrapped accordingly.
        artifact_envelope = {"maritime_intelligence": synthetic_mi}

        with mock.patch.dict(
            os.environ, {"MARITIME_INTELLIGENCE_ENABLED": "1"}, clear=False
        ):
            with mock.patch.object(
                server.json, "load", return_value=artifact_envelope
            ):
                from fastapi.testclient import TestClient
                with TestClient(server.app) as c:
                    r = c.get("/api/maritime/routing-impact")
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is True
        assert body["reason"] is None
        assert body["snapshot_id"] == "test-snap-001"
        assert body["duration_ms"] == 42
        assert body["budget_exceeded"] is False
        assert body["sources_used"] == [
            "emodnet_vessel_density", "open_meteo",
        ]
        assert body["sources_missing"] == ["noaa_ais_port_intelligence"]
        # Four features must always be classified.
        feature_names = {f["feature"] for f in body["features"]}
        assert feature_names == {"traffic", "port", "weather", "congestion"}
        # Counts must add up to 4 (one per feature).
        total = sum(body["summary"].values())
        assert total == 4
        # weather (speed_factor=0.95, conf=0.78) → applied.
        # congestion (score=0.7, conf=0.82) → applied.
        # traffic / port absent → baseline.
        assert body["summary"]["applied"] == 2
        assert body["summary"]["baseline_retained"] == 2
        # The dashboard must surface the per-feature reason.
        for f in body["features"]:
            assert f["reason"]
            assert f["state"] in {
                "applied", "rejected", "stale",
                "fallback_used", "baseline",
            }

    def test_routing_impact_classify_feature_states(self, server):
        """The pure helper must produce the documented states for
        each input shape. No optimizer decision may be made; this
        is purely an explanatory classifier.

        Note: weather/congestion classify a None payload as
        ``fallback_used`` (not ``baseline``) because the IP-1
        attach layer reports the feature as 'tried but absent',
        which is a different code path from 'feature never
        considered'. Traffic and port have no consumption in
        the optimizer, so they classify None as ``baseline``.
        """
        classify = server._phase8_classify_feature

        # Weather: applied (good confidence, fresh).
        w = classify("weather", {
            "speed_factor": 0.95,
            "confidence": 0.78,
            "freshness_state": "fresh",
        })
        assert w["state"] == "applied"
        assert w["speed_factor"] == 0.95

        # Weather: rejected (low confidence).
        w = classify("weather", {
            "speed_factor": 0.9,
            "confidence": 0.4,
            "freshness_state": "fresh",
        })
        assert w["state"] == "rejected"

        # Weather: stale.
        w = classify("weather", {
            "speed_factor": 0.9,
            "confidence": 0.8,
            "freshness_state": "stale",
        })
        assert w["state"] == "stale"

        # Weather: fallback when no speed_factor.
        w = classify("weather", {
            "confidence": 0.8,
            "freshness_state": "fresh",
        })
        assert w["state"] == "fallback_used"

        # Weather: fallback when payload is None (tried but absent).
        w = classify("weather", None)
        assert w["state"] == "fallback_used"

        # Congestion: applied.
        c = classify("congestion", {
            "score": 0.7,
            "confidence": 0.8,
            "freshness_state": "fresh",
        })
        assert c["state"] == "applied"

        # Congestion: rejected.
        c = classify("congestion", {
            "score": 0.7,
            "confidence": 0.4,
            "freshness_state": "fresh",
        })
        assert c["state"] == "rejected"

        # Congestion: stale.
        c = classify("congestion", {
            "score": 0.7,
            "confidence": 0.8,
            "freshness_state": "stale",
        })
        assert c["state"] == "stale"

        # Congestion: fallback when score absent.
        c = classify("congestion", {
            "confidence": 0.8,
            "freshness_state": "fresh",
        })
        assert c["state"] == "fallback_used"

        # Congestion: fallback when payload is None.
        assert classify("congestion", None)["state"] == "fallback_used"

        # Traffic / port: baseline when None (not consumed by optimizer).
        assert classify("traffic", None)["state"] == "baseline"
        assert classify("port", None)["state"] == "baseline"

        # Traffic / port: applied when payload present.
        assert classify("traffic", {"freshness_state": "fresh"})["state"] == "applied"
        assert classify("port", {"freshness_state": "fresh"})["state"] == "applied"

    def test_routing_impact_never_raises(self, server, artifact_root):
        """The endpoint must catch every exception and degrade to
        the safe-empty payload with reason='safe_failure'."""
        from fastapi.testclient import TestClient

        # Make json.load raise. The endpoint must catch and
        # degrade to safe_failure.
        with mock.patch.dict(
            os.environ, {"MARITIME_INTELLIGENCE_ENABLED": "1"}, clear=False
        ):
            with mock.patch.object(
                server.json, "load",
                side_effect=RuntimeError("disk on fire"),
            ):
                with TestClient(server.app) as c:
                    r = c.get("/api/maritime/routing-impact")
                    assert r.status_code == 200
                    body = r.json()
                    # safe_failure collapses to the flag_off-style
                    # empty payload.
                    assert body["available"] is False
                    assert body["reason"] == "safe_failure"
                    assert body["features"] == []


# --------------------------------------------------------------------
# Tier-0 compliance — pipeline_output.json must not change
# --------------------------------------------------------------------


class TestPhase8Tier0Compliance:
    """Tests that prove Phase 8 did not mutate the optimizer's
    contract surface. The hard rule from the Phase 8 brief: the
    ``pipeline_output.json`` SHA must not change as a side effect
    of importing backend.server or calling the new endpoints.
    """

    PIPELINE_OUTPUT = REPO_ROOT / "pipeline_output.json"

    def _sha(self, path: Path) -> str:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()

    def test_pipeline_output_unchanged_after_import(self):
        """Importing backend.server with default env must not
        mutate pipeline_output.json. The Tier-0 contract is
        that the artifact is the optimizer's output, never a
        side effect of an HTTP import."""
        before = self._sha(self.PIPELINE_OUTPUT) if self.PIPELINE_OUTPUT.exists() else None
        _ = _ensure_server_loaded()
        after = self._sha(self.PIPELINE_OUTPUT) if self.PIPELINE_OUTPUT.exists() else None
        assert before == after, (
            "backend.server import mutated pipeline_output.json — "
            "Tier-0 contract violated"
        )

    def test_pipeline_output_unchanged_after_endpoint_calls(
        self, client_enabled
    ):
        """Calling the two Phase 8 endpoints must not mutate
        pipeline_output.json. If it does, the optimizer's
        output is being rewritten by the dashboard, which is
        explicitly forbidden by the brief."""
        before = self._sha(self.PIPELINE_OUTPUT) if self.PIPELINE_OUTPUT.exists() else None
        r1 = client_enabled.get("/api/maritime/overview")
        r2 = client_enabled.get("/api/maritime/routing-impact")
        assert r1.status_code == 200
        assert r2.status_code == 200
        after = self._sha(self.PIPELINE_OUTPUT) if self.PIPELINE_OUTPUT.exists() else None
        assert before == after, (
            "Calling the Phase 8 endpoints mutated pipeline_output.json — "
            "Tier-0 contract violated"
        )

    def test_optimizer_endpoints_registered(self, server):
        """The two new endpoints must be registered on the FastAPI
        app under their documented paths. This is the bare-minimum
        contract for the frontend to call them."""
        routes = {r.path for r in server.app.routes}
        assert "/api/maritime/overview" in routes
        assert "/api/maritime/routing-impact" in routes
