"""SQLite-backed spatial index for traffic records.

We do NOT introduce a new dependency — Python's stdlib ships ``sqlite3``.
The index is optional; the feature adapter prefers it for bbox lookups and
falls back to a linear scan if absent.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from ..schemas.traffic_density import TrafficDensityRecord


_SCHEMA = """
CREATE TABLE IF NOT EXISTS traffic (
    spatial_id TEXT NOT NULL,
    latitude   REAL NOT NULL,
    longitude  REAL NOT NULL,
    vessel_class TEXT NOT NULL,
    intensity  REAL NOT NULL,
    observed_at TEXT NOT NULL,
    snapshot_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_traffic_lat_lon
    ON traffic(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_traffic_spatial
    ON traffic(spatial_id);
"""


class SqliteTrafficIndex:
    """Thin wrapper around sqlite3 for the traffic table.

    The index is intentionally read-mostly; ``add_records`` performs a
    single transaction per call. No data is mutated outside this class.
    """

    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def add_records(self, records: Iterable[TrafficDensityRecord]) -> int:
        rows = [
            (
                r.spatial_id, r.latitude, r.longitude,
                r.vessel_class.value, r.intensity, r.observed_at, r.snapshot_id,
            )
            for r in records
        ]
        if not rows:
            return 0
        with self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO traffic "
                "(spatial_id, latitude, longitude, vessel_class, intensity, observed_at, snapshot_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def query_bbox(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        *,
        vessel_class: Optional[str] = None,
        limit: int = 10000,
    ) -> List[Tuple[str, float, float, str, float, str, str]]:
        """Return rows whose lat/lon is within the bbox. Cap at ``limit``."""
        params: List = [min_lat, max_lat, min_lon, max_lon]
        where = "latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?"
        if vessel_class:
            where += " AND vessel_class = ?"
            params.append(vessel_class)
        params.append(limit)
        cur = self._conn.execute(
            f"SELECT spatial_id, latitude, longitude, vessel_class, intensity, observed_at, snapshot_id "
            f"FROM traffic WHERE {where} LIMIT ?",
            params,
        )
        return list(cur.fetchall())

    def count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM traffic")
        return int(cur.fetchone()[0])
