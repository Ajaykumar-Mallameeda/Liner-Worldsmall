"""Phase 5 — Weather intelligence package.

A production-safe, provenance-aware, failure-resistant weather
intelligence layer. The package is the only place in the project
that knows about weather data sources; the rest of the system sees
only the canonical :class:`maritime.schemas.weather.WeatherObservation`
and the immutable local snapshots produced by
:mod:`maritime.weather.orchestrator`.

Architectural invariants:

* One canonical schema (no provider-specific types leak out).
* One snapshot publication mechanism (:mod:`maritime.snapshot_publisher`).
* One source-health mechanism (:class:`maritime.schemas.intelligence.SourceStatus`).
* One provenance mechanism (:mod:`maritime.quality.provenance`).
* One telemetry namespace (``maritime_*`` from :mod:`maritime.telemetry`).
* One read-only FeatureAdapter boundary.
* Network access is funneled through :class:`maritime.live.http_client.BoundedHttpClient`
  (shared with Phase 4). Tests assert that no other module imports
  ``urllib`` / ``socket``.
* Weather never enters the optimizer directly; the optimizer may
  only consume already-materialized local snapshots.
"""

from __future__ import annotations

__all__: list[str] = []
