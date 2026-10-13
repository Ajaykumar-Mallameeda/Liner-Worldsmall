"""Phase 4 — Live maritime ingestion package.

The ``maritime.live`` package is the live ingestion counterpart of the
existing :mod:`maritime.ingestion` package. It introduces the live
provider abstraction while reusing the existing snapshot, freshness,
verification, and telemetry layers.

The optimizer MUST NOT import anything from this package. Live data
becomes an immutable local snapshot before the rest of the system
can see it.
"""
