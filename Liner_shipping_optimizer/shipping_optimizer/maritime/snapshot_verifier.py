"""Phase 3 — Snapshot verification.

Independent verifier for snapshot files. Validates:

    * Existence + non-empty
    * SHA-256 checksum against the manifest
    * Required metadata fields
    * Schema version compatibility
    * Source identifier / dataset identifier sanity

The verifier is pure (no I/O mutation) and never raises for benign
reasons. It returns a structured :class:`VerificationResult` instead.

It is independent of the publisher so that the publisher and the
verifier can disagree safely (one is the writer, the other is the
auditor).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .snapshot_publisher import _sha256_file, canonical_json_bytes


def _sha256_bytes(data: bytes) -> str:
    """SHA-256 of a bytes payload."""
    import hashlib
    return hashlib.sha256(data).hexdigest()


# Required fields for a published manifest.
REQUIRED_MANIFEST_FIELDS: Tuple[str, ...] = (
    "schema_version",
    "snapshot_id",
    "dataset",
    "source",
    "created_at",
    "checksum_records",
    "checksum_manifest",
)

# Required fields for a published metadata file.
REQUIRED_METADATA_FIELDS: Tuple[str, ...] = (
    "snapshot_id",
    "source",
    "dataset",
    "created_at",
    "schema_version",
    "record_count",
    "accepted_records",
    "rejected_records",
    "quality_score",
    "source_health",
)


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of a verification pass.

    ``reasons`` is a list of human-readable failure reasons. Empty
    when ``ok`` is True.
    """
    ok: bool
    reasons: List[str] = field(default_factory=list)
    sha256_records: Optional[str] = None
    sha256_manifest: Optional[str] = None
    size_bytes_records: int = 0
    size_bytes_manifest: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "sha256_records": self.sha256_records,
            "sha256_manifest": self.sha256_manifest,
            "size_bytes_records": self.size_bytes_records,
            "size_bytes_manifest": self.size_bytes_manifest,
        }


# --------------------------------------------------------------------
# Manifest / metadata parsing
# --------------------------------------------------------------------


def _read_json(path: Path) -> Optional[Mapping[str, Any]]:
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _missing_fields(obj: Mapping[str, Any], required: Sequence[str]) -> List[str]:
    return [name for name in required if name not in obj or obj.get(name) in (None, "", [])]


# --------------------------------------------------------------------
# Public verifier
# --------------------------------------------------------------------


def verify_snapshot_directory(
    snapshot_dir: Path,
    *,
    records_filename: str = "traffic_density.jsonl",
    manifest_filename: str = "manifest.json",
    metadata_filename: str = "metadata.json",
    compatible_schema_versions: Optional[Sequence[str]] = None,
) -> VerificationResult:
    """Verify a snapshot directory in place.

    The verifier checks (in order):

        1. ``manifest.json`` exists, parses, has all required fields.
        2. ``metadata.json`` exists, parses, has all required fields.
        3. Schema version is in ``compatible_schema_versions`` (when given).
        4. The records file SHA-256 matches ``checksum_records``.
        5. The manifest SHA-256 matches ``checksum_manifest``.
    """
    reasons: List[str] = []

    manifest = _read_json(snapshot_dir / manifest_filename)
    metadata = _read_json(snapshot_dir / metadata_filename)

    if manifest is None:
        reasons.append("manifest_unreadable")
    else:
        missing = _missing_fields(manifest, REQUIRED_MANIFEST_FIELDS)
        if missing:
            reasons.append(f"manifest_missing_fields:{','.join(missing)}")

    if metadata is None:
        reasons.append("metadata_unreadable")
    else:
        missing = _missing_fields(metadata, REQUIRED_METADATA_FIELDS)
        if missing:
            reasons.append(f"metadata_missing_fields:{','.join(missing)}")

    # Schema compatibility.
    if compatible_schema_versions is not None and manifest is not None:
        schema_v = str(manifest.get("schema_version", ""))
        if schema_v not in compatible_schema_versions:
            reasons.append(f"schema_incompatible:{schema_v}")

    # Cross-consistency between manifest and metadata.
    if manifest is not None and metadata is not None:
        if manifest.get("snapshot_id") and metadata.get("snapshot_id"):
            if manifest.get("snapshot_id") != metadata.get("snapshot_id"):
                reasons.append("snapshot_id_mismatch")
        if manifest.get("dataset") and metadata.get("dataset"):
            if manifest.get("dataset") != metadata.get("dataset"):
                reasons.append("dataset_mismatch")
        if manifest.get("source") and metadata.get("source"):
            if manifest.get("source") != metadata.get("source"):
                reasons.append("source_mismatch")
        if manifest.get("schema_version") and metadata.get("schema_version"):
            if manifest.get("schema_version") != metadata.get("schema_version"):
                reasons.append("schema_version_mismatch")

    # Records checksum.
    records_path = snapshot_dir / records_filename
    records_sha: Optional[str] = None
    records_size = 0
    if not records_path.exists():
        reasons.append("records_missing")
    else:
        records_sha = _sha256_file(records_path)
        records_size = records_path.stat().st_size
        if manifest is not None:
            expected = manifest.get("checksum_records")
            if expected and expected != records_sha:
                reasons.append("checksum_records_mismatch")

    # Manifest checksum (self-referential).
    # The manifest embeds its own SHA-256, so we can't re-hash the file
    # directly. Instead we canonicalize the manifest with the
    # ``checksum_manifest`` field stripped and compare the resulting
    # digest to the embedded value. This makes the self-referential
    # checksum well-defined and stable across re-publishes.
    manifest_sha: Optional[str] = None
    manifest_size = 0
    if manifest is not None and (snapshot_dir / manifest_filename).exists():
        manifest_path = snapshot_dir / manifest_filename
        manifest_sha = _sha256_file(manifest_path)
        manifest_size = manifest_path.stat().st_size
        expected = manifest.get("checksum_manifest")
        if expected:
            body = dict(manifest)
            body.pop("checksum_manifest", None)
            body_sha = _sha256_bytes(canonical_json_bytes(body))
            if body_sha != expected:
                reasons.append("checksum_manifest_mismatch")

    return VerificationResult(
        ok=not reasons,
        reasons=reasons,
        sha256_records=records_sha,
        sha256_manifest=manifest_sha,
        size_bytes_records=records_size,
        size_bytes_manifest=manifest_size,
    )
