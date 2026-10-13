"""Phase 6 — Congestion intelligence package.

The package is the only place in the project that produces
congestion records. The rest of the system sees only the
canonical :class:`maritime.schemas.congestion.CongestionRecord`
and the immutable local snapshots produced by
:mod:`maritime.congestion.orchestrator`.

Architectural invariants (shared with Phases 1–5):

* One canonical schema.
* One snapshot publication mechanism.
* One source-health mechanism.
* One provenance mechanism.
* One telemetry namespace.
* One read-only FeatureAdapter boundary.
* Network access is funneled through
  :class:`maritime.live.http_client.BoundedHttpClient` (shared with
  Phase 4). Tests assert that no other module imports
  ``urllib`` / ``socket``.

Congestion is DERIVED DATA. The layer reads only already-materialized
local snapshots from Phases 1–5; it never opens a network connection
itself. Future optimizer integration (IP-3) is explicitly out of scope
for Phase 6.
"""

from __future__ import annotations

__all__: list[str] = []
