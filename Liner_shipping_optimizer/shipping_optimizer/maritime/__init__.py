"""Maritime Intelligence Foundation (Phase 1 + Phase 2 + Phase 3).

The maritime package is the single ingestion/normalization/feature-adapter
boundary for external maritime data. It lives OUTSIDE ``src/`` by design —
``tests/architecture/test_network_isolation.py`` enforces that the optimizer
import graph has zero maritime footprint. Any future network-capable code for
external data sources must live here, not in ``src/``.

Phase 1 surfaces:

    ingestion      -> normalized records
    normalization  -> canonical schema
    quality        -> metadata + provenance
    storage        -> local immutable snapshots
    intelligence   -> derived features
    feature_adapter-> read-only interface for future consumers (optimizer, dashboard)

Phase 2 adds:

    schemas.vessel_position -> canonical AIS-style record
    schemas.port            -> port geofence + port-call records
    ingestion.noaa          -> NOAA MarineCadastre AIS adapter (local mode)
    geofencing              -> deterministic port geofence helpers
    port_call_extractor     -> port-call state machine
    intelligence.port_activity -> port-activity derived features
    pipeline_noaa           -> end-to-end NOAA pipeline
    port_adapter            -> read-only Phase 2 adapter

Phase 3 adds the RESILIENCE CORE (no live network, no optimizer mutation):

    snapshot_publisher        -> atomic temp-write + checksum + rename
    snapshot_verifier         -> independent checksum / schema / metadata audit
    schema_registry           -> per-dataset schema-version compatibility
    freshness_policy          -> deterministic freshness state machine
    fallback_resolver         -> strict 5-tier deterministic fallback
    snapshot_rollback         -> read-side rollback plan (no live mutation)
    safe_feature_adapter      -> resilience wrapper over the Phase 1/2 adapters

The optimizer MUST consume the read-only ``feature_adapter`` /
``port_adapter`` / ``safe_feature_adapter`` and nothing else. Direct calls
into ingestion/storage are forbidden at the optimizer level.
"""

__all__ = [
    "schemas",
    "ingestion",
    "normalization",
    "quality",
    "storage",
    "intelligence",
    "feature_adapter",
    "geofencing",
    "port_call_extractor",
    "port_adapter",
    "pipeline_noaa",
    "snapshot_publisher",
    "snapshot_verifier",
    "schema_registry",
    "freshness_policy",
    "fallback_resolver",
    "snapshot_rollback",
    "safe_feature_adapter",
]
