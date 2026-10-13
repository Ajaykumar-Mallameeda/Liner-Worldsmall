"""Snapshot storage layout and manifest management.

A snapshot is a directory under ``data/maritime/snapshots/<dataset>/<snapshot_id>/``
with the following contents:

    metadata.json       — human-readable summary (records, quality, etc.)
    manifest.json       — machine-readable descriptor + checksums
    traffic_density.jsonl — canonical records (one per line)
    traffic_index.db    — optional SQLite index for lookups by spatial_id

The directory is created atomically: every file is written to a ``.tmp``
sibling and renamed on success. Once a snapshot is on disk it is immutable;
new data creates a new snapshot.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from ..schemas.intelligence import TrafficIntelligenceSnapshot
from .jsonl_store import write_jsonl, read_jsonl


# --------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------


# Default base directory, overridable for tests.
DEFAULT_SNAPSHOT_BASE = Path("data/maritime/snapshots")


@dataclass(frozen=True)
class SnapshotPaths:
    """Resolved on-disk paths for a single snapshot."""
    base: Path
    dataset: str
    snapshot_id: str

    @property
    def root(self) -> Path:
        return self.base / self.dataset / self.snapshot_id

    @property
    def metadata(self) -> Path:
        return self.root / "metadata.json"

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def records(self) -> Path:
        return self.root / "traffic_density.jsonl"

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
    with open(tmp, "wb") as f:
        f.write(data)
    tmp.replace(path)


def generate_snapshot_id(*, dataset: str, created_at: Optional[datetime] = None) -> str:
    """Deterministic snapshot id: ``<dataset_short>_<utc>_<8hex>``.

    The 8-hex suffix is a random suffix to avoid collisions when two
    snapshots are created at the same wall-clock second. This is
    deterministic for the same inputs modulo the random suffix.
    """
    dt = created_at or datetime.now(tz=timezone.utc)
    suffix = uuid.uuid4().hex[:8]
    # Replace underscores in the dataset name so the id always splits into
    # exactly three parts on the underscore.
    short = dataset.split("_")[0]
    return f"{short}_{dt.strftime('%Y%m%dT%H%M%SZ')}_{suffix}"


# --------------------------------------------------------------------
# Store
# --------------------------------------------------------------------


class SnapshotStore:
    """High-level store API.

    The store is intentionally simple: callers hand it a fully-constructed
    :class:`TrafficIntelligenceSnapshot`; the store writes it to disk and
    returns the :class:`SnapshotPaths` for later loading. Loading is by
    snapshot_id (latest valid snapshot is the convention for the adapter).
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base = Path(base_dir) if base_dir is not None else DEFAULT_SNAPSHOT_BASE

    @property
    def base_dir(self) -> Path:
        return self._base

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(self, snapshot: TrafficIntelligenceSnapshot, *, dataset_key: Optional[str] = None) -> SnapshotPaths:
        """Atomically write a snapshot. Returns the paths written.

        If ``dataset_key`` is provided it overrides the on-disk dataset
        directory name. This lets the caller group snapshots from
        different source datasets under a single, canonical key (e.g.
        the adapter looks under ``emodnet_vessel_density`` regardless of
        what the source called its own product).
        """
        key = dataset_key or snapshot.dataset
        paths = SnapshotPaths(base=self._base, dataset=key, snapshot_id=snapshot.snapshot_id)
        paths.ensure()

        # 1) records
        record_dicts = [r.to_dict() for r in snapshot.records]
        records_summary = write_jsonl(paths.records, record_dicts)

        # 2) manifest
        manifest = {
            "schema_version": snapshot.schema_version,
            "snapshot_id": snapshot.snapshot_id,
            "dataset": snapshot.dataset,
            "source": snapshot.source,
            "dataset_version": snapshot.dataset_version,
            "created_at": snapshot.created_at,
            "observed_start": snapshot.observed_start,
            "observed_end": snapshot.observed_end,
            "record_count": snapshot.record_count,
            "accepted_records": snapshot.accepted_records,
            "rejected_records": snapshot.rejected_records,
            "duplicate_records": snapshot.duplicate_records,
            "quality_score": snapshot.quality_score,
            "completeness_ratio": snapshot.completeness_ratio,
            "freshness": snapshot.freshness,
            "source_status": snapshot.source_status.value,
            "quality_status": snapshot.quality_status.value,
            "license": snapshot.license,
            "attribution": snapshot.attribution,
            "provenance": dict(snapshot.provenance),
            "features": [f.to_dict() for f in snapshot.features],
            "hotspots": [h.to_dict() for h in snapshot.hotspots],
            "checksum_records": records_summary["checksum"],
            "checksum_manifest": "",  # filled below
        }
        _atomic_write_json(paths.manifest, manifest)
        manifest["checksum_manifest"] = _hash_file(paths.manifest)
        _atomic_write_json(paths.manifest, manifest)  # rewrite with own hash

        # 3) metadata
        metadata = snapshot.to_metadata_dict()
        metadata["files"] = {
            "records": str(paths.records.relative_to(self._base.parent)),
            "manifest": str(paths.manifest.relative_to(self._base.parent)),
        }
        _atomic_write_json(paths.metadata, metadata)

        return paths

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_snapshots(self, dataset: str) -> List[SnapshotPaths]:
        d = self._base / dataset
        if not d.is_dir():
            return []
        out: List[SnapshotPaths] = []
        for child in sorted(d.iterdir()):
            if child.is_dir() and (child / "manifest.json").exists():
                out.append(SnapshotPaths(base=self._base, dataset=dataset, snapshot_id=child.name))
        return out

    def latest(self, dataset: str) -> Optional[SnapshotPaths]:
        snapshots = self.list_snapshots(dataset)
        return snapshots[-1] if snapshots else None

    def load_manifest(self, paths: SnapshotPaths) -> Dict[str, Any]:
        return json.loads(paths.manifest.read_text(encoding="utf-8"))

    def load_records(self, paths: SnapshotPaths) -> List[Dict[str, Any]]:
        return list(read_jsonl(paths.records))

    def verify_checksum(self, paths: SnapshotPaths) -> bool:
        """Verify the records file checksum matches the manifest.

        Returns ``True`` if the file exists and its SHA-256 matches the
        recorded manifest value, or if the file is missing (no records to
        verify). Returns ``False`` on a real mismatch.
        """
        if not paths.records.exists():
            return True
        manifest = self.load_manifest(paths)
        expected = manifest.get("checksum_records")
        if not expected:
            return False
        actual = _hash_file(paths.records)
        return actual == expected
