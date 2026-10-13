"""Tests for the port-intelligence feature derivations."""

from maritime.intelligence.port_activity import (
    compute_port_activity,
    compute_port_call_timeline,
    compute_port_vessel_type_mix,
)
from maritime.schemas.port import Port, PortCall, PortCallStatus, PortType


def _port(pid="USLAX"):
    return Port(
        port_id=pid, name=pid, country="US", region="r",
        latitude=33.74, longitude=-118.26, radius_nm=1.5,
        port_type=PortType.CARGO, source="S", dataset="D",
        dataset_version="0", license="CC0", attribution="",
    )


def _call(pid, mmsi, vt, dwell, status=PortCallStatus.CONFIRMED):
    return PortCall(
        port_call_id=f"pc:{pid}-{mmsi}",
        mmsi=mmsi, port_id=pid,
        arrival_ts="2024-06-01T08:00:00+00:00",
        departure_ts="2024-06-01T12:00:00+00:00" if dwell > 0 else None,
        dwell_minutes=dwell,
        status=status, vessel_type=vt,
        nav_status_at_arrival="moored",
        source="S", dataset="D", dataset_version="0",
        ingested_at="2024-06-01T00:00:00+00:00",
        snapshot_id="s", quality=1.0, license="CC0", attribution="NOAA",
        provenance={},
    )


def test_compute_port_activity_empty():
    assert compute_port_activity([], {"USLAX": _port()}) == []
    assert compute_port_vessel_type_mix([], {"USLAX": _port()}) == []
    assert compute_port_call_timeline([], {"USLAX": _port()}) == []


def test_compute_port_activity_basic():
    p = _port()
    calls = [
        _call("USLAX", "338000001", "cargo", 240),
        _call("USLAX", "338000002", "tanker", 180),
        _call("USLAX", "338000003", "cargo", 60, status=PortCallStatus.REJECTED),
    ]
    activity = compute_port_activity(calls, {"USLAX": p})
    assert len(activity) == 1
    a = activity[0]
    assert a.port_id == "USLAX"
    assert a.call_count == 3
    assert a.confirmed_count == 2
    assert a.rejected_count == 1
    assert a.unique_vessels == 3
    assert a.avg_dwell_minutes > 0


def test_compute_port_vessel_type_mix():
    p = _port()
    calls = [
        _call("USLAX", "338000001", "cargo", 240),
        _call("USLAX", "338000002", "cargo", 180),
        _call("USLAX", "338000003", "tanker", 100),
    ]
    mix = compute_port_vessel_type_mix(calls, {"USLAX": p})
    assert len(mix) == 1
    m = mix[0]
    assert m.dominant_type == "cargo"
    assert m.sample_size == 3
    assert m.counts_by_type["cargo"] == 2


def test_compute_port_vessel_type_mix_skips_rejected():
    p = _port()
    calls = [
        _call("USLAX", "338000001", "cargo", 240),
        _call("USLAX", "338000002", "cargo", 60, status=PortCallStatus.REJECTED),
    ]
    mix = compute_port_vessel_type_mix(calls, {"USLAX": p})
    assert mix[0].sample_size == 1


def test_compute_port_call_timeline_skips_rejected():
    p = _port()
    calls = [
        _call("USLAX", "338000001", "cargo", 240),
        _call("USLAX", "338000002", "cargo", 60, status=PortCallStatus.REJECTED),
    ]
    timeline = compute_port_call_timeline(calls, {"USLAX": p})
    assert len(timeline) == 1
    assert timeline[0].mmsi == "338000001"


def test_compute_port_call_timeline_chronological():
    p = _port()
    c1 = _call("USLAX", "338000002", "cargo", 200)
    c2 = _call("USLAX", "338000001", "cargo", 100)
    # Override arrival timestamps so the chronological order is non-trivial.
    import dataclasses
    c1 = dataclasses.replace(c1, arrival_ts="2024-06-01T09:00:00+00:00")
    c2 = dataclasses.replace(c2, arrival_ts="2024-06-01T08:00:00+00:00")
    timeline = compute_port_call_timeline([c1, c2], {"USLAX": p})
    assert timeline[0].mmsi == "338000001"
    assert timeline[1].mmsi == "338000002"