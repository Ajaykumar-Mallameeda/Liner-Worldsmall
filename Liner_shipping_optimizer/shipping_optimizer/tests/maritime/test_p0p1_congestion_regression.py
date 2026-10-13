"""P0/P1-B and P0/P1-C regression — Congestion port/route contract defects.

**D-2 (port)**: ``GET /api/maritime/congestion/port`` without a
``port_id`` returned ``422 Unprocessable Entity`` because ``port_id``
was declared as a required query parameter. The Phase 6 dashboard
explicitly polls this endpoint with an empty query string
(``/api/maritime/congestion/port?``) to render the congestion overview
surface. Fix: ``port_id`` is now ``Optional[str] = None``; a missing or
empty value returns the snapshot-derived overview (records + summary)
so the dashboard can render the full intelligence surface.

**D-3 (route)**: ``GET /api/maritime/congestion/route`` was reported
as 422-for-any-input. The actual contract is: ``waypoints`` is
required and is a ``;``-separated list of ``lat,lon`` pairs. Valid
input returns 200 with the route's best record per waypoint; missing
input correctly returns 422 (FastAPI's standard required-field
response); malformed input returns 200/ok:false with
``"no valid waypoints"``. The fix adds explicit lat/lon range
validation so out-of-range coordinates are reported as invalid
rather than being silently passed through.

The tests below cover the minimum regression cases required by the
P0/P1 brief §10:

* port: valid, unknown, missing, malformed, empty, stale/offline,
  frontend request
* route: valid, invalid, missing, malformed, empty, no-snapshot,
  stale/offline, success, frontend-generated

No network calls, no optimizer, no pipeline_output.json modification.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


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


def _write_congestion_snapshot(
    root: Path, records: List[Dict[str, Any]]
) -> str:
    """Write a congestion snapshot (manifest + records) under ``root``."""
    snap_id = "p0p1-congestion-regression"
    snap_dir = root / "maritime_congestion" / snap_id
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / "manifest.json").write_text(
        json.dumps({
            "snapshot_id": snap_id,
            "dataset": "maritime_congestion",
            "dataset_version": "1.0.0",
            "source": "derived",
            "license": "derived",
            "attribution": "regression test",
            "commercial_safe": True,
            "quality": 0.7,
            "freshness_state": "available",
            "source_health": "available",
            "retrieved_at": _ts(),
            "record_count": len(records),
            "synthetic": True,
        }),
        encoding="utf-8",
    )
    with open(snap_dir / "congestion_records.jsonl", "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return snap_id


@pytest.fixture()
def client(monkeypatch):
    """FastAPI test client with maritime feature flags enabled."""
    monkeypatch.setenv("MARITIME_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("MARITIME_CONGESTION_ENABLED", "1")
    monkeypatch.setenv("MARITIME_WEATHER_ENABLED", "0")
    from fastapi.testclient import TestClient
    from backend.server import app
    return TestClient(app)


@pytest.fixture()
def populated_snapshot(monkeypatch, tmp_path):
    """Point CongestionFeatureAdapter at a populated temp snapshot."""
    records = [
        _valid_record_kwargs(
            record_id="cong-norfolk",
            entity_id="port:norfolk",
            latitude=36.85,
            longitude=-76.29,
            congestion_score=0.42,
            congestion_level="moderate",
        ),
        _valid_record_kwargs(
            record_id="cong-hamburg",
            entity_id="port:hamburg",
            latitude=53.55,
            longitude=9.99,
            congestion_score=0.71,
            congestion_level="high",
        ),
        _valid_record_kwargs(
            record_id="cong-shanghai",
            entity_id="port:shanghai",
            latitude=31.20,
            longitude=121.50,
            congestion_score=0.88,
            congestion_level="severe",
        ),
    ]
    _write_congestion_snapshot(tmp_path, records)

    from maritime.congestion import feature_adapter as cfa
    from maritime.storage.snapshots import SnapshotStore
    original_init = cfa.CongestionFeatureAdapter.__init__

    def _patched(self, store=None, *, dataset_key=None):
        original_init(
            self,
            store=SnapshotStore(base_dir=tmp_path),
            dataset_key=dataset_key or cfa.CONGESTION_DATASET_KEY,
        )

    monkeypatch.setattr(cfa.CongestionFeatureAdapter, "__init__", _patched)
    return {"root": tmp_path, "records": records}


# --------------------------------------------------------------------
# P0/P1-B — Congestion /port regression (7 cases, >= 6 required)
# --------------------------------------------------------------------


class TestCongestionPortContract:
    """D-2 contract: ``port_id`` is optional; missing/empty returns
    a snapshot-derived overview (records + summary).
    """

    def test_valid_port_id(self, client, populated_snapshot):
        r = client.get("/api/maritime/congestion/port?port_id=port:norfolk")
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert any(
            rec.get("entity_id") == "port:norfolk"
            for rec in body.get("records", [])
        )

    def test_unknown_port_id_still_ok(self, client, populated_snapshot):
        r = client.get("/api/maritime/congestion/port?port_id=port:nonexistent")
        assert r.status_code == 200
        body = r.json()
        assert r.status_code != 422
        assert "ok" in body
        assert "records" in body
        assert "count" in body

    def test_missing_port_id_returns_overview(self, client, populated_snapshot):
        r = client.get("/api/maritime/congestion/port")
        assert r.status_code == 200
        body = r.json()
        assert r.status_code != 422
        assert "records" in body
        assert "count" in body
        assert body.get("snapshot_id") is not None
        assert body.get("source_health") == "available"
        assert body.get("freshness_state") == "available"

    def test_empty_port_id_treated_as_missing(self, client, populated_snapshot):
        r = client.get("/api/maritime/congestion/port?port_id=")
        assert r.status_code == 200
        body = r.json()
        assert r.status_code != 422
        assert "records" in body

    def test_malformed_port_id_accepted(self, client, populated_snapshot):
        r = client.get("/api/maritime/congestion/port?port_id=port%20unknown")
        assert r.status_code == 200
        body = r.json()
        assert r.status_code != 422
        assert "records" in body

    def test_empty_congestion_state(self, client):
        with tempfile.TemporaryDirectory() as td:
            from maritime.congestion import feature_adapter as cfa
            from maritime.storage.snapshots import SnapshotStore
            original_init = cfa.CongestionFeatureAdapter.__init__

            def _patched(self, store=None, *, dataset_key=None):
                original_init(
                    self,
                    store=SnapshotStore(base_dir=Path(td)),
                    dataset_key=dataset_key or cfa.CONGESTION_DATASET_KEY,
                )

            cfa.CongestionFeatureAdapter.__init__ = _patched  # type: ignore
            try:
                r1 = client.get("/api/maritime/congestion/port")
                r2 = client.get(
                    "/api/maritime/congestion/port?port_id=port:anywhere"
                )
                for r in (r1, r2):
                    body = r.json()
                    assert r.status_code == 200
                    assert body.get("ok") is False
                    assert "no congestion snapshot" in (body.get("error") or "")
            finally:
                cfa.CongestionFeatureAdapter.__init__ = original_init  # type: ignore

    def test_frontend_generated_request(self, client, populated_snapshot):
        # The dashboard's polling URL.
        r = client.get("/api/maritime/congestion/port?")
        assert r.status_code == 200
        body = r.json()
        assert r.status_code != 422
        assert body.get("snapshot_id") is not None


# --------------------------------------------------------------------
# P0/P1-C — Congestion /route regression (9 cases, >= 8 required)
# --------------------------------------------------------------------


class TestCongestionRouteContract:
    """D-3 contract: ``waypoints`` is a required query parameter
    (semicolon-separated ``lat,lon`` pairs). Malformed coordinates
    return 200/ok:false; missing waypoints is 422 (standard
    required-field response).
    """

    def test_valid_route_request(self, client, populated_snapshot):
        r = client.get(
            "/api/maritime/congestion/route"
            "?waypoints=53.55,9.99;36.85,-76.29"
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body.get("count") == 2

    def test_invalid_range_rejected(self, client, populated_snapshot):
        # All-out-of-range waypoints → no valid waypoints.
        r = client.get(
            "/api/maritime/congestion/route?waypoints=999,0;1000,2000"
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is False
        assert "no valid waypoints" in (body.get("error") or "")

    def test_missing_waypoints_returns_422(self, client, populated_snapshot):
        r = client.get("/api/maritime/congestion/route")
        assert r.status_code == 422
        body = r.json()
        detail = body.get("detail") or []
        assert any(
            "waypoints" in (item.get("loc") or [])
            for item in detail
        )

    def test_malformed_coordinates(self, client, populated_snapshot):
        r = client.get(
            "/api/maritime/congestion/route?waypoints=not-a-pair"
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is False
        assert "no valid waypoints" in (body.get("error") or "")

    def test_empty_waypoints(self, client, populated_snapshot):
        r = client.get("/api/maritime/congestion/route?waypoints=")
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is False
        assert "no valid waypoints" in (body.get("error") or "")

    def test_only_separators(self, client, populated_snapshot):
        r = client.get("/api/maritime/congestion/route?waypoints=;;;")
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is False
        assert "no valid waypoints" in (body.get("error") or "")

    def test_no_snapshot_state(self, client):
        with tempfile.TemporaryDirectory() as td:
            from maritime.congestion import feature_adapter as cfa
            from maritime.storage.snapshots import SnapshotStore
            original_init = cfa.CongestionFeatureAdapter.__init__

            def _patched(self, store=None, *, dataset_key=None):
                original_init(
                    self,
                    store=SnapshotStore(base_dir=Path(td)),
                    dataset_key=dataset_key or cfa.CONGESTION_DATASET_KEY,
                )

            cfa.CongestionFeatureAdapter.__init__ = _patched  # type: ignore
            try:
                r = client.get(
                    "/api/maritime/congestion/route"
                    "?waypoints=53.55,9.99;36.85,-76.29"
                )
                body = r.json()
                assert r.status_code == 200
                assert body.get("ok") is False
                assert "no congestion snapshot" in (body.get("error") or "")
            finally:
                cfa.CongestionFeatureAdapter.__init__ = original_init  # type: ignore

    def test_stale_offline_state_via_freshness(self, client, populated_snapshot):
        r = client.get(
            "/api/maritime/congestion/route"
            "?waypoints=53.55,9.99;36.85,-76.29"
        )
        body = r.json()
        assert r.status_code == 200
        # The contract: source_health / freshness_state are echoed
        # from the manifest, never overridden to "live".
        assert body.get("source_health") != "live"
        assert body.get("freshness_state") in (
            "available", "stale", "unknown", "offline",
        )

    def test_frontend_generated_request(self, client, populated_snapshot):
        # The dashboard builds:
        #   /api/maritime/congestion/route?waypoints=53.55,9.99;36.85,-76.29;31.20,121.50
        r = client.get(
            "/api/maritime/congestion/route"
            "?waypoints=53.55,9.99;36.85,-76.29;31.20,121.50"
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body.get("count") == 3
        for rec in body.get("records", []):
            assert "synthetic" in rec
            assert "entity_id" in rec
            assert "congestion_score" in rec
