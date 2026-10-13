"""Phase 3 — Safe feature adapter.

A read-only, fail-safe wrapper around the existing
:class:`maritime.FeatureAdapter` and
:class:`maritime.port_adapter.PortFeatureAdapter` that never raises
and always returns the deterministic empty payload when:

    * the master feature flag is OFF
    * the snapshot store is empty
    * the on-disk snapshot fails verification
    * a freshness/quality gate fails
    * a schema-incompatible snapshot is on disk

The safe adapter is the single entry point that downstream consumers
(dashboard, API, future optimizer IP-1) should use in Phase 3. The
underlying :class:`FeatureAdapter` is preserved for direct Phase 1/2
backward compatibility, but the safe adapter enforces the resilience
contract.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .fallback_resolver import (
    FallbackDecision,
    FallbackTier,
    empty_feature_dict,
    resolve_snapshot_fallback,
    safe_failure_payload,
)
from .feature_adapter import (
    FeatureAdapter,
    maritime_intelligence_enabled,
    maritime_traffic_enabled,
)
from .freshness_policy import (
    FreshnessConfig,
    FreshnessState,
    evaluate,
)
from .port_adapter import (
    NOAA_DATASET_KEY,
    PortFeatureAdapter,
    maritime_port_enabled,
)
from .schema_registry import SchemaRegistry
from .snapshot_verifier import (
    REQUIRED_MANIFEST_FIELDS,
    REQUIRED_METADATA_FIELDS,
    verify_snapshot_directory,
)
from . import telemetry


# Default dataset key for the EMODnet traffic snapshot.
EMODNET_DATASET_KEY = "emodnet_vessel_density"


@dataclass(frozen=True)
class ResilientReadResult:
    """Result of a safe read against a dataset."""
    dataset: str
    decision: FallbackDecision
    payload: Dict[str, Any]
    records: List[Dict[str, Any]]  # empty unless tier == FRESH or STALE_WITHIN_WINDOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "decision": self.decision.to_dict(),
            "payload": self.payload,
            "records_count": len(self.records),
        }


class SafeFeatureAdapter:
    """Resilience wrapper over the Phase 1/2 feature adapters.

    All public methods are read-only and never raise. The constructor
    accepts the same ``SnapshotStore`` as the underlying adapters so
    they share a single on-disk root.
    """

    def __init__(
        self,
        store: Optional[Any] = None,
        *,
        snapshot_root: Optional[Path] = None,
        schema_registry: Optional[SchemaRegistry] = None,
        freshness_config: Optional[FreshnessConfig] = None,
    ) -> None:
        self._registry = schema_registry or SchemaRegistry.with_defaults()
        self._freshness = freshness_config or FreshnessConfig()
        self._traffic = FeatureAdapter(store=store)
        self._port: Optional[PortFeatureAdapter] = None
        if store is not None:
            try:
                self._port = PortFeatureAdapter(store=store)
            except Exception:
                self._port = None
        # Snapshot root resolution: prefer the store's base, else default.
        if snapshot_root is not None:
            self._root = Path(snapshot_root)
        elif store is not None and getattr(store, "base_dir", None) is not None:
            self._root = Path(store.base_dir)
        else:
            from .storage.snapshots import DEFAULT_SNAPSHOT_BASE
            self._root = Path(DEFAULT_SNAPSHOT_BASE)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, dataset: str) -> FallbackDecision:
        return resolve_snapshot_fallback(
            dataset=dataset,
            snapshot_root=self._root,
            registry=self._registry,
            config=self._freshness,
        )

    def _read_records(self, snapshot_dir: Path) -> List[Dict[str, Any]]:
        # Two layouts: traffic_density.jsonl (Phase 1) and
        # vessel_positions.jsonl (Phase 2). We yield whichever exists.
        from .storage.jsonl_store import read_jsonl
        out: List[Dict[str, Any]] = []
        for fname in ("traffic_density.jsonl", "vessel_positions.jsonl", "port_calls.jsonl"):
            p = snapshot_dir / fname
            if p.exists():
                for rec in read_jsonl(p, on_error=lambda *_: None):
                    out.append(rec)
        return out

    def _payload_from_decision(
        self, dataset: str, decision: FallbackDecision
    ) -> Dict[str, Any]:
        base = empty_feature_dict()
        if decision.snapshot_dir is None:
            return {**base, "dataset": dataset, "tier": decision.tier.value}
        snap = decision.snapshot_dir
        meta_path = snap / "metadata.json"
        if not meta_path.exists():
            return {**base, "dataset": dataset, "tier": decision.tier.value}
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {**base, "dataset": dataset, "tier": decision.tier.value}
        freshness_dict = decision.freshness.to_dict() if decision.freshness else None
        verification_dict = (
            decision.verification.to_dict() if decision.verification else None
        )
        return {
            "enabled": True,
            "fresh": decision.tier == FallbackTier.FRESH,
            "state": (
                decision.freshness.state.value
                if decision.freshness
                else FreshnessState.OFFLINE.value
            ),
            "tier": decision.tier.value,
            "dataset": dataset,
            "source": meta.get("source"),
            "snapshot_id": meta.get("snapshot_id"),
            "created_at": meta.get("created_at"),
            "record_count": int(meta.get("record_count", 0) or 0),
            "accepted_records": int(meta.get("accepted_records", 0) or 0),
            "quality_score": meta.get("quality_score"),
            "freshness_label": freshness_dict.get("state") if freshness_dict else None,
            "schema_version": meta.get("schema_version"),
            "checksum": (
                verification_dict.get("sha256_records")
                if verification_dict
                else None
            ),
            "degraded_reasons": (
                verification_dict.get("reasons", []) if verification_dict else []
            ),
            "freshness": freshness_dict,
            "verification": verification_dict,
            "notes": decision.notes,
        }

    def _emit_safe_read(
        self,
        *,
        dataset: str,
        decision: FallbackDecision,
        event: str = "maritime_snapshot_read",
    ) -> None:
        try:
            telemetry.record(
                event,
                dataset=dataset,
                status="ok" if decision.tier in (FallbackTier.FRESH, FallbackTier.STALE_WITHIN_WINDOW, FallbackTier.KNOWN_GOOD_HISTORICAL) else "warn",
                extras={
                    "tier": decision.tier.value,
                    "snapshot_dir": (
                        str(decision.snapshot_dir) if decision.snapshot_dir else None
                    ),
                    "state": (
                        decision.freshness.state.value if decision.freshness else None
                    ),
                },
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def is_master_enabled(self) -> bool:
        return maritime_intelligence_enabled()

    def is_traffic_enabled(self) -> bool:
        return maritime_traffic_enabled()

    def is_port_enabled(self) -> bool:
        return maritime_port_enabled()

    def get_status(self) -> Dict[str, Any]:
        """Aggregate status for both traffic and port datasets."""
        traffic_decision = self._resolve(EMODNET_DATASET_KEY)
        port_decision = self._resolve(NOAA_DATASET_KEY)
        return {
            "enabled": self.is_master_enabled(),
            "traffic_enabled": self.is_traffic_enabled(),
            "port_enabled": self.is_port_enabled(),
            "traffic": self._payload_from_decision(
                EMODNET_DATASET_KEY, traffic_decision
            ),
            "port": self._payload_from_decision(NOAA_DATASET_KEY, port_decision),
            "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    def get_source_health(self) -> Dict[str, Any]:
        """Compact health view for the dashboard / API."""
        status = self.get_status()
        return {
            "enabled": status["enabled"],
            "traffic": {
                "state": status["traffic"]["state"],
                "tier": status["traffic"]["tier"],
                "snapshot_id": status["traffic"]["snapshot_id"],
                "fresh": status["traffic"]["fresh"],
                "degraded_reasons": status["traffic"]["degraded_reasons"],
            },
            "port": {
                "state": status["port"]["state"],
                "tier": status["port"]["tier"],
                "snapshot_id": status["port"]["snapshot_id"],
                "fresh": status["port"]["fresh"],
                "degraded_reasons": status["port"]["degraded_reasons"],
            },
            "evaluated_at": status["evaluated_at"],
        }

    def get_traffic_snapshot(self) -> ResilientReadResult:
        if not self.is_master_enabled() or not self.is_traffic_enabled():
            decision = FallbackDecision(
                tier=FallbackTier.EMPTY,
                snapshot_dir=None,
                freshness=None,
                verification=None,
                notes="flag_off",
            )
            payload = empty_feature_dict("flag_off")
            payload["dataset"] = EMODNET_DATASET_KEY
            return ResilientReadResult(
                dataset=EMODNET_DATASET_KEY, decision=decision,
                payload=payload, records=[],
            )
        decision = self._resolve(EMODNET_DATASET_KEY)
        payload = self._payload_from_decision(EMODNET_DATASET_KEY, decision)
        records = self._read_records(decision.snapshot_dir) if decision.snapshot_dir else []
        self._emit_safe_read(dataset=EMODNET_DATASET_KEY, decision=decision)
        return ResilientReadResult(
            dataset=EMODNET_DATASET_KEY,
            decision=decision,
            payload=payload,
            records=records,
        )

    def get_port_snapshot(self) -> ResilientReadResult:
        if not self.is_master_enabled() or not self.is_port_enabled():
            decision = FallbackDecision(
                tier=FallbackTier.EMPTY,
                snapshot_dir=None,
                freshness=None,
                verification=None,
                notes="flag_off",
            )
            payload = empty_feature_dict("flag_off")
            payload["dataset"] = NOAA_DATASET_KEY
            return ResilientReadResult(
                dataset=NOAA_DATASET_KEY, decision=decision,
                payload=payload, records=[],
            )
        decision = self._resolve(NOAA_DATASET_KEY)
        payload = self._payload_from_decision(NOAA_DATASET_KEY, decision)
        records = self._read_records(decision.snapshot_dir) if decision.snapshot_dir else []
        self._emit_safe_read(
            dataset=NOAA_DATASET_KEY,
            decision=decision,
            event="maritime_port_snapshot_read",
        )
        return ResilientReadResult(
            dataset=NOAA_DATASET_KEY,
            decision=decision,
            payload=payload,
            records=records,
        )
