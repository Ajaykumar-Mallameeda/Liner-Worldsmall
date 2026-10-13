"""Tier-0 consumer check, backend half: execute the REAL backend consumers of a pipeline result.

The backend server (``backend/server.py``) loads ``pipeline_output.json`` from the project root
and serves it through ``/api/metrics/summary``, ``/api/regions/`` and ``/api/pipeline/iterations``
(computing the displayed margin itself).  This script copies a snapshot of the project, puts a
REAL orchestrator output at its root (scenario ``real``) - and, for the boundary cases a real run
does not produce, outputs DERIVED from it by ``tier0_scenarios.py`` (clearly named ``derived_*``;
they test how a consumer treats an edge value, they are not evidence about the optimiser) - starts the app under FastAPI's TestClient and records every
response.  Nothing is simulated: the server code that runs is the production module.

usage: python -I tier0_backend.py <snapshot_root> <scenarios_dir (tier0_scenarios.py)> <out.json>
"""
import copy
import importlib
import json
import sys
import traceback
from pathlib import Path

ROOT, REAL, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(ROOT))

SCEN_DIR = REAL                                  # second argument: the scenarios directory
SCENARIOS = {f.stem: (lambda f=f: json.loads(f.read_text(encoding="utf-8")))
             for f in sorted(SCEN_DIR.glob("*.json")) if not f.name.startswith("_")}

out = {"source": str(REAL), "scenarios": {}, "errors": []}
try:
    from fastapi.testclient import TestClient
    import backend.server as srv
except Exception as exc:                                              # noqa: BLE001
    out["errors"].append({"stage": "import", "error": f"{type(exc).__name__}: {exc}",
                          "trace": traceback.format_exc()})
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    sys.exit(0)

target = ROOT / "pipeline_output.json"
for name, build in SCENARIOS.items():
    data = build()
    target.write_text(json.dumps(data), encoding="utf-8")
    rec = {"endpoints": {}, "executive_summary_verdict_line": None}
    summ = data.get("executive_summary", "")
    for line in summ.splitlines():
        if "Verdict" in line or "ACCOUNTING NOT VERIFIED" in line or "margin" in line.lower():
            rec["executive_summary_verdict_line"] = (rec["executive_summary_verdict_line"] or "") + line.strip() + " | "
    rec["decision_layer"] = {
        "network_ledger_verified": data["network_ledger"].get("verified"),
        "ledger_margin": data["network_ledger"]["weekly_usd"].get("profit_margin_on_revenue"),
        "regional_margins": {r["region"]: r.get("profit_margin_pct") for r in data["regional_results"]},
        "regional_verdicts": {r["region"]: next((l.strip() for l in (r.get("explanation") or "").splitlines()
                                                if l.startswith("Verdict")), None)
                              for r in data["regional_results"]},
        "evaluation_margin_verdict": (data.get("decision_output", {}).get("evaluation", {}) or {}).get(
            "margin_verdict"),
    }
    try:
        srv.current_state["regions"], srv.current_state["iterations"] = {}, []
        ok = srv.load_pipeline_data()
        rec["load_pipeline_data"] = ok
        try:
            from backend.routes import metrics as route_metrics
            rec["routes_metrics_profit_margin"] = route_metrics._derive_metrics_from_pipeline()["profit_margin"]
        except Exception as exc:                                      # noqa: BLE001
            rec["routes_metrics_error"] = f"{type(exc).__name__}: {exc}"
        with TestClient(srv.app) as client:
            for ep in ("/api/metrics/summary", "/api/regions/", "/api/pipeline/iterations"):
                r = client.get(ep)
                body = r.json()
                if ep == "/api/metrics/summary":                      # keep the consumer-relevant part
                    m = body.get("metrics", {})
                    body = {"metrics": {k: m.get(k) for k in ("weeklyProfit", "annualProfit", "totalCost",
                                                              "coverage", "margin", "totalServices")},
                            "status": m.get("status"), "executive_summary": m.get("executive_summary")}
                rec["endpoints"][ep] = {"status_code": r.status_code, "body": body}
    except Exception as exc:                                          # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["trace"] = traceback.format_exc()
    out["scenarios"][name] = rec

# a real output is left in place by the loop: restore the project's own state (no output file)
OUT.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
print("scenarios:", {k: ("error" if "error" in v else "ok") for k, v in out["scenarios"].items()})
