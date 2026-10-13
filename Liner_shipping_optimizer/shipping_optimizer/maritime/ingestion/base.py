"""Provider interface and shared types for maritime ingestion.

The base class is intentionally tiny: providers produce *raw* records (JSON
dicts) from an external source. Normalization happens in the next stage.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


class IngestionError(Exception):
    """Raised by providers when ingestion fails. The error message is a
    short, machine-readable reason; details belong in the result object.
    """


@dataclass
class IngestionResult:
    """The output of a provider call.

    Attributes:
        source: canonical source name (e.g. ``"EMODNET"``)
        dataset: source-specific dataset identifier
        dataset_version: version string from the source
        records: list of raw record dicts (not yet normalized to canonical)
        license: verified license string, or ``"unresolved"``
        attribution: verified attribution string, or ``""``
        retrieved_at: ISO-8601 UTC timestamp of when retrieval happened
        observed_period: ``{"start": ..., "end": ...}`` ISO-8601 UTC strings
        source_url: original URL or local path of the source
        notes: human-readable notes (e.g. ``"synthetic-fixture"``)
    """
    source: str
    dataset: str
    dataset_version: str
    records: List[Dict[str, Any]]
    license: str
    attribution: str
    retrieved_at: str
    observed_period: Dict[str, str]
    source_url: str
    notes: str = ""

    def is_empty(self) -> bool:
        return not self.records


class BaseIngestionProvider(abc.ABC):
    """Abstract base class for ingestion providers.

    The contract is:
        1. The provider may make network calls (it lives in the maritime
           ingestion boundary).
        2. It must be deterministic given the same inputs.
        3. It must respect the configured timeout.
        4. It must never block forever (no infinite retries).
        5. It must return an ``IngestionResult`` even on partial failure
           (with empty records and a non-empty ``notes`` field).
    """

    source: str = "ABSTRACT"

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = float(timeout_seconds)

    @abc.abstractmethod
    def fetch(self) -> IngestionResult:
        """Fetch from the configured source and return raw records."""

    def load_local(self, path: str) -> IngestionResult:
        """Optional local/offline mode.

        Default implementation: read the path as a JSON file and adapt it.
        Subclasses may override to support more elaborate offline formats.
        """
        import json
        from pathlib import Path
        from datetime import datetime, timezone
        p = Path(path)
        if not p.exists():
            raise IngestionError(f"local source not found: {path}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise IngestionError(f"local source is not valid JSON: {e}") from e
        records = data.get("records") if isinstance(data, dict) else data
        if records is None:
            raise IngestionError("local source has no 'records' field")
        if not isinstance(records, list):
            raise IngestionError("local source 'records' must be a list")
        return IngestionResult(
            source=data.get("source", self.source) if isinstance(data, dict) else self.source,
            dataset=data.get("dataset", "unknown") if isinstance(data, dict) else "unknown",
            dataset_version=data.get("dataset_version", "0.0.0") if isinstance(data, dict) else "0.0.0",
            records=list(records),
            license=data.get("license", "unresolved") if isinstance(data, dict) else "unresolved",
            attribution=data.get("attribution", "") if isinstance(data, dict) else "",
            retrieved_at=data.get("retrieved_at", datetime.now(tz=timezone.utc).isoformat()) if isinstance(data, dict) else datetime.now(tz=timezone.utc).isoformat(),
            observed_period=data.get("observed_period", {"start": datetime.now(tz=timezone.utc).isoformat(), "end": datetime.now(tz=timezone.utc).isoformat()}) if isinstance(data, dict) else {"start": datetime.now(tz=timezone.utc).isoformat(), "end": datetime.now(tz=timezone.utc).isoformat()},
            source_url=str(path),
            notes="local-fixture",
        )
