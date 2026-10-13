"""Local immutable snapshot storage for maritime intelligence.

Phase 1 ships two on-disk representations:

* :mod:`jsonl_store`  — one record per line, simple and human-readable
* :mod:`sqlite_store` — single-file database for indexable lookups

The :mod:`snapshots` module ties everything together: it owns the on-disk
layout (``data/maritime/snapshots/<dataset>/<snapshot_id>/``) and produces
the manifest + metadata files that consumers read.
"""

from .snapshots import SnapshotStore, SnapshotPaths
from .jsonl_store import write_jsonl, read_jsonl, compute_line_checksum
from .sqlite_store import SqliteTrafficIndex

__all__ = [
    "SnapshotStore",
    "SnapshotPaths",
    "write_jsonl",
    "read_jsonl",
    "compute_line_checksum",
    "SqliteTrafficIndex",
]
