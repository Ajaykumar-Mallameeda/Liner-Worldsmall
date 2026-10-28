#!/usr/bin/env python3
"""Write frontend/public/benchmark/seed30_bundle.json: the frozen benchmark exactly as the API serves it.

The Benchmarks tab reads /api/benchmark/summary and /api/benchmark/<dataset>/seeds; when no backend is
reachable (e.g. ``npm run dev`` without the API) it falls back to this file. Both are produced by the same
functions (backend/run_catalog.py), so the two sources cannot drift apart; re-run after the benchmark changes:

    python scripts/build_benchmark_bundle.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import run_catalog  # noqa: E402


def main() -> int:
    summary = run_catalog._read_json(run_catalog.FULL_SUMMARY)
    if not summary:
        print(f"benchmark summary not found: {run_catalog.FULL_SUMMARY}", file=sys.stderr)
        return 1
    seeds = {key: run_catalog._seed_rows(d) for key, d in run_catalog._datasets().items()}
    bundle = {
        "bundle_generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "backend/run_catalog.py over " + str(run_catalog.BENCHMARK_ROOT.relative_to(ROOT)).replace("\\", "/"),
        "summary": {k: v for k, v in summary.items() if k != "root"},
        "seeds": seeds,
    }
    out = ROOT / "frontend" / "public" / "benchmark" / "seed30_bundle.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1024:.0f} KB, "
          f"{sum(len(v) for v in seeds.values())} seed rows over {len(seeds)} datasets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
