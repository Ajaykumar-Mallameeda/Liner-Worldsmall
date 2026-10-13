"""JSONL-based record storage.

A simple, deterministic, append-only format used to persist snapshot
records. Each line is a JSON object terminated by a newline. Empty lines
are ignored on read.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional


def compute_line_checksum(line: bytes) -> str:
    """SHA-256 of a single line (without the trailing newline)."""
    return hashlib.sha256(line.rstrip(b"\n")).hexdigest()


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Write records as JSONL. Returns a small summary dict.

    Atomic write: data is written to a temp file and renamed on success.
    The returned ``checksum`` is the SHA-256 of the full file content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    n = 0
    h = hashlib.sha256()
    with open(tmp, "wb") as f:
        for rec in records:
            line = json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8")
            f.write(line)
            f.write(b"\n")
            h.update(line)
            h.update(b"\n")
            n += 1
    tmp.replace(path)
    return {"records": n, "checksum": h.hexdigest()}


def read_jsonl(path: Path, *, on_error: Optional[Callable[[int, Exception], None]] = None) -> Iterator[Dict[str, Any]]:
    """Yield records from a JSONL file. Skip empty lines.

    If a line fails to parse, behavior depends on ``on_error``:
        - if provided, it is called with (line_number, exception) and iteration continues
        - if not provided, the exception is re-raised
    """
    if not path.exists():
        return
    with open(path, "rb") as f:
        lineno = 0
        for raw in f:
            lineno += 1
            line = raw.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                if on_error is None:
                    raise
                on_error(lineno, e)


def load_all(path: Path) -> List[Dict[str, Any]]:
    """Convenience wrapper that materializes all records into a list."""
    return list(read_jsonl(path))
