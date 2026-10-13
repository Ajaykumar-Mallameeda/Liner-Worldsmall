import { useEffect, useMemo, useState } from "react";
import CongestionIntelligenceCard from "../components/maritime/CongestionIntelligenceCard.jsx";
import IntelligencePanel from "../components/maritime/primitives/IntelligencePanel.jsx";
import IntelligenceSurfaceHeader from "../components/maritime/IntelligenceSurfaceHeader.jsx";
import ProvenanceStrip from "../components/maritime/ProvenanceStrip.jsx";
import MaritimeStatusBadge from "../components/maritime/primitives/MaritimeStatusBadge.jsx";
import OperationalTable from "../components/maritime/primitives/OperationalTable.jsx";

/**
 * MaritimeCongestionView
 * ----------------------
 * Phase 6 congestion intelligence surface. Polls
 *   - /api/maritime/congestion/status
 *   - /api/maritime/congestion/snapshot
 *   - /api/maritime/congestion/hotspots
 * and exposes on-demand queries to /at, /port, /route. Phase 8
 * swapped the ad-hoc glass divs for IntelligencePanel, the
 * records table for OperationalTable, and the inline status
 * pills for MaritimeStatusBadge. The data plumbing, the
 * summary computation, and the on-demand query boxes are
 * unchanged.
 */

const LEVEL_COLOR = {
  low: "#10b981",
  moderate: "#38bdf8",
  high: "#f59e0b",
  severe: "#ef4444",
};

function number(v, digits = 2) {
  if (v == null) return "—";
  if (typeof v !== "number") return String(v);
  return v.toFixed(digits);
}

function Components({ components, missing }) {
  if (!components || typeof components !== "object") {
    return <span className="text-white/30">—</span>;
  }
  const keys = ["traffic", "traffic_change", "port_pressure", "weather_risk"];
  return (
    <div className="space-y-1">
      {keys.map((k) => {
        const v = Number(components[k]) || 0;
        return (
          <div key={k} className="flex items-center gap-2">
            <span className="text-[10px] text-white/40 font-mono w-28">
              {k}
            </span>
            <div
              className="flex-1 h-1.5 rounded"
              style={{ background: "rgba(255,255,255,0.06)" }}
            >
              <div
                className="h-1.5 rounded transition-all duration-500"
                style={{
                  width: `${Math.round(Math.max(0, Math.min(1, v)) * 100)}%`,
                  background: "#00d4ff",
                }}
              />
            </div>
            <span className="text-[10px] text-white/60 font-mono w-10 text-right">
              {v.toFixed(2)}
            </span>
          </div>
        );
      })}
      {(missing || []).length > 0 && (
        <div className="flex flex-wrap gap-1 pt-1">
          {(missing || []).map((m) => (
            <span
              key={m}
              className="text-[9px] font-mono px-1 rounded"
              style={{
                background: "rgba(255,255,255,0.05)",
                color: "#94a3b8",
              }}
            >
              {m}·missing
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function LevelPill({ level }) {
  const color = LEVEL_COLOR[level] || "#64748b";
  return (
    <span
      className="text-[10px] font-mono px-1 rounded"
      style={{
        background: `${color}1a`,
        color: color,
        border: `1px solid ${color}33`,
      }}
    >
      {(level || "—").toUpperCase()}
    </span>
  );
}

function FreshnessPill({ state }) {
  return (
    <span
      className="text-[10px] font-mono"
      style={{ color: 'rgba(255,255,255,0.55)' }}
    >
      {(state || "unknown").toLowerCase()}
    </span>
  );
}

export default function MaritimeCongestionView() {
  const [status, setStatus] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [hotspots, setHotspots] = useState(null);
  const [atQuery, setAtQuery] = useState({ lat: 53.55, lon: 9.99, radius_km: 200.0 });
  const [atResult, setAtResult] = useState(null);
  const [portQuery, setPortQuery] = useState("");
  const [portResult, setPortResult] = useState(null);
  const [routeText, setRouteText] = useState("53.55,9.99;36.85,-76.29;31.20,121.50");
  const [routeResult, setRouteResult] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchAll = async () => {
      try {
        const [sResp, snapResp, hResp, sumResp] = await Promise.all([
          fetch("/api/maritime/congestion/status").catch(() => null),
          fetch("/api/maritime/congestion/snapshot?limit=200").catch(() => null),
          fetch("/api/maritime/congestion/hotspots?threshold=0.65&limit=10").catch(() => null),
          fetch("/api/maritime/congestion/port?").catch(() => null),
        ]);
        if (cancelled) return;
        if (sResp && sResp.ok) setStatus(await sResp.json());
        if (snapResp && sResp.ok) {
          const j = await snapResp.json();
          setSnapshot(j);
        }
        if (hResp && hResp.ok) setHotspots(await hResp.json());
        if (sumResp && sumResp.ok) {
          // intentionally unused — see summary memo below.
        }
      } catch (_) {
        if (!cancelled) setStatus({ enabled: false });
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchAll();
    const t = setInterval(fetchAll, 15000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  // Compute summary from the snapshot inline.
  const summary = useMemo(() => {
    if (!snapshot || !snapshot.records) return null;
    const records = snapshot.records;
    const levels = { low: 0, moderate: 0, high: 0, severe: 0 };
    const scores = [];
    const confs = [];
    let syntheticCount = 0;
    for (const r of records) {
      if (r.congestion_level in levels) levels[r.congestion_level] += 1;
      if (typeof r.congestion_score === "number") scores.push(r.congestion_score);
      if (typeof r.confidence === "number") confs.push(r.confidence);
      if (r.synthetic) syntheticCount += 1;
    }
    const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
    const avgC = confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : 0;
    const max = scores.length ? Math.max(...scores) : 0;
    return {
      entity_count: records.length,
      by_level: levels,
      average_score: avg,
      average_confidence: avgC,
      max_score: max,
      synthetic: syntheticCount === records.length && records.length > 0,
      records: [{
        entity_count: records.length,
        by_level: levels,
        average_score: avg,
        average_confidence: avgC,
        max_score: max,
        synthetic: syntheticCount === records.length && records.length > 0,
      }],
    };
  }, [snapshot]);

  const runAt = async () => {
    try {
      const u =
        `/api/maritime/congestion/at?lat=${atQuery.lat}&lon=${atQuery.lon}` +
        `&radius_km=${atQuery.radius_km}&limit=4`;
      const r = await fetch(u);
      if (r.ok) setAtResult(await r.json());
    } catch (_) {
      setAtResult({ ok: false, records: [], error: "request_failed" });
    }
  };

  const runPort = async () => {
    if (!portQuery.trim()) {
      setPortResult(null);
      return;
    }
    try {
      const r = await fetch(
        `/api/maritime/congestion/port?port_id=${encodeURIComponent(portQuery.trim())}`
      );
      if (r.ok) setPortResult(await r.json());
    } catch (_) {
      setPortResult({ ok: false, records: [], error: "request_failed" });
    }
  };

  const runRoute = async () => {
    if (!routeText.trim()) {
      setRouteResult(null);
      return;
    }
    try {
      const r = await fetch(
        `/api/maritime/congestion/route?waypoints=${encodeURIComponent(routeText.trim())}`
      );
      if (r.ok) setRouteResult(await r.json());
    } catch (_) {
      setRouteResult({ ok: false, records: [], error: "request_failed" });
    }
  };

  return (
    <div className="space-y-5">
      <IntelligenceSurfaceHeader
        eyebrow="Operations · Congestion Intelligence"
        title="Congestion Intelligence"
        subtitle="Phase 6 congestion layer. Synthetic data is clearly labelled; the dashboard never presents a fixture as a production read."
        overallState={status?.state || (status?.enabled === false ? "disabled" : "offline")}
        evaluatedAt={status?.evaluated_at}
      />

      <CongestionIntelligenceCard status={status} summary={summary} hotspots={hotspots} />

      {/* Records table */}
      <IntelligencePanel
        title="Congestion Records (first 50)"
        density="compact"
        right={
          snapshot && snapshot.metadata ? (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-white/30 font-mono">
                {snapshot.metadata.snapshot_id || "—"}
              </span>
              {snapshot.metadata.synthetic && (
                <MaritimeStatusBadge value="checking" pulse={false} />
              )}
            </div>
          ) : null
        }
      >
        <OperationalTable
          columns={[
            {
              key: "entity",
              label: "entity",
              render: (r) => r.entity_id || r.record_id || "—",
            },
            {
              key: "level",
              label: "level",
              render: (r) => <LevelPill level={r.congestion_level} />,
            },
            {
              key: "score",
              label: "score",
              align: "right",
              render: (r) => number(r.congestion_score),
            },
            {
              key: "confidence",
              label: "confidence",
              align: "right",
              render: (r) => number(r.confidence),
            },
            {
              key: "freshness",
              label: "freshness",
              render: (r) => <FreshnessPill state={r.freshness_state} />,
            },
            {
              key: "synthetic",
              label: "synthetic",
              render: (r) => r.synthetic ? "yes" : "no",
            },
            {
              key: "components",
              label: "components",
              render: (r) => (
                <Components
                  components={r.components}
                  missing={r.missing_inputs}
                />
              ),
              minWidth: 280,
            },
            {
              key: "missing",
              label: "missing",
              render: (r) => (r.missing_inputs || []).join(", ") || "—",
            },
          ]}
          rows={(snapshot && snapshot.records ? snapshot.records : []).slice(0, 50)}
          rowKey="record_id"
          density="compact"
          maxHeight={420}
          loading={loading}
          emptyMessage="No records."
        />
      </IntelligencePanel>

      <div className="grid grid-cols-3 gap-4">
        {/* At-coord */}
        <IntelligencePanel
          title="At Coordinate"
          density="comfortable"
        >
          <div className="grid grid-cols-3 gap-2 mb-2">
            <label className="text-[10px] font-mono text-white/30">
              lat
              <input
                type="number"
                step="0.01"
                value={atQuery.lat}
                onChange={(e) =>
                  setAtQuery((q) => ({ ...q, lat: parseFloat(e.target.value) }))
                }
                className="w-full mt-1 bg-transparent text-white/80 font-mono text-xs px-2 py-1 rounded"
                style={{ border: "1px solid rgba(255,255,255,0.1)" }}
              />
            </label>
            <label className="text-[10px] font-mono text-white/30">
              lon
              <input
                type="number"
                step="0.01"
                value={atQuery.lon}
                onChange={(e) =>
                  setAtQuery((q) => ({ ...q, lon: parseFloat(e.target.value) }))
                }
                className="w-full mt-1 bg-transparent text-white/80 font-mono text-xs px-2 py-1 rounded"
                style={{ border: "1px solid rgba(255,255,255,0.1)" }}
              />
            </label>
            <label className="text-[10px] font-mono text-white/30">
              radius (km)
              <input
                type="number"
                step="10"
                value={atQuery.radius_km}
                onChange={(e) =>
                  setAtQuery((q) => ({ ...q, radius_km: parseFloat(e.target.value) }))
                }
                className="w-full mt-1 bg-transparent text-white/80 font-mono text-xs px-2 py-1 rounded"
                style={{ border: "1px solid rgba(255,255,255,0.1)" }}
              />
            </label>
          </div>
          <button
            onClick={runAt}
            className="text-xs font-mono px-3 py-1 rounded"
            style={{
              background: "rgba(0,212,255,0.12)",
              color: "#00d4ff",
              border: "1px solid rgba(0,212,255,0.3)",
            }}
          >
            Query
          </button>
          <div className="mt-3 space-y-1 max-h-48 overflow-y-auto">
            {atResult && atResult.records && atResult.records.length > 0 ? (
              atResult.records.map((r, i) => (
                <div
                  key={i}
                  className="text-[11px] font-mono text-white/60 py-1"
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                >
                  <div className="text-white/40">
                    {r.entity_id || r.record_id || "?"} — {number(r.latitude)},{number(r.longitude)}
                  </div>
                  <div>
                    level {(r.congestion_level || "—").toUpperCase()} · score {number(r.congestion_score)} · conf {number(r.confidence)}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-[11px] font-mono text-white/30">
                {atResult ? "No records near this coordinate." : "Run a query to see results."}
              </div>
            )}
          </div>
        </IntelligencePanel>

        {/* Port */}
        <IntelligencePanel
          title="Port Lookup"
          density="comfortable"
        >
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={portQuery}
              onChange={(e) => setPortQuery(e.target.value)}
              placeholder="port_id (e.g. USNYC)"
              className="flex-1 bg-transparent text-white/80 font-mono text-xs px-2 py-1 rounded"
              style={{ border: "1px solid rgba(255,255,255,0.1)" }}
            />
            <button
              onClick={runPort}
              className="text-xs font-mono px-3 py-1 rounded"
              style={{
                background: "rgba(0,212,255,0.12)",
                color: "#00d4ff",
                border: "1px solid rgba(0,212,255,0.3)",
              }}
            >
              Query
            </button>
          </div>
          <div className="mt-3 space-y-1 max-h-48 overflow-y-auto">
            {portResult && portResult.records && portResult.records.length > 0 ? (
              portResult.records.map((r, i) => (
                <div
                  key={i}
                  className="text-[11px] font-mono text-white/60 py-1"
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                >
                  <div className="text-white/40">
                    {r.entity_id || r.record_id || "?"} — {number(r.latitude)},{number(r.longitude)}
                  </div>
                  <div>
                    level {(r.congestion_level || "—").toUpperCase()} · score {number(r.congestion_score)}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-[11px] font-mono text-white/30">
                {portResult ? "No record for this port." : "Enter a port_id to query."}
              </div>
            )}
          </div>
        </IntelligencePanel>

        {/* Route preview */}
        <IntelligencePanel
          title="Route Preview"
          density="comfortable"
        >
          <input
            type="text"
            value={routeText}
            onChange={(e) => setRouteText(e.target.value)}
            placeholder="lat,lon;lat,lon;..."
            className="w-full bg-transparent text-white/80 font-mono text-xs px-2 py-1 rounded"
            style={{ border: "1px solid rgba(255,255,255,0.1)" }}
          />
          <button
            onClick={runRoute}
            className="mt-2 text-xs font-mono px-3 py-1 rounded"
            style={{
              background: "rgba(0,212,255,0.12)",
              color: "#00d4ff",
              border: "1px solid rgba(0,212,255,0.3)",
            }}
          >
            Query
          </button>
          <div className="mt-3 space-y-1 max-h-48 overflow-y-auto">
            {routeResult && routeResult.records && routeResult.records.length > 0 ? (
              routeResult.records.map((r, i) => (
                <div
                  key={i}
                  className="text-[11px] font-mono text-white/60 py-1"
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                >
                  <div className="text-white/40">
                    {r.entity_id || r.record_id || "?"} — {number(r.latitude)},{number(r.longitude)}
                  </div>
                  <div>
                    level {(r.congestion_level || "—").toUpperCase()} · score {number(r.congestion_score)}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-[11px] font-mono text-white/30">
                {routeResult ? "No waypoint matches within radius." : "Enter waypoints to preview."}
              </div>
            )}
          </div>
        </IntelligencePanel>
      </div>

      {/* Hotspot list */}
      {hotspots && hotspots.records && hotspots.records.length > 0 && (
        <IntelligencePanel
          title="High-Congestion Hotspots"
          density="compact"
        >
          <div className="grid grid-cols-3 gap-3">
            {hotspots.records.map((r, i) => (
              <div
                key={i}
                className="rounded p-3"
                style={{
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid rgba(255,255,255,0.05)",
                }}
              >
                <div className="text-xs font-mono text-white/80">
                  {r.entity_id || r.record_id || "?"}
                </div>
                <div
                  className="text-[10px] font-mono"
                  style={{ color: LEVEL_COLOR[r.congestion_level] || "#94a3b8" }}
                >
                  {(r.congestion_level || "—").toUpperCase()} · {number(r.congestion_score)}
                </div>
                <div className="text-[10px] font-mono text-white/40 mt-1">
                  {number(r.latitude, 2)},{number(r.longitude, 2)} · conf {number(r.confidence)}
                </div>
              </div>
            ))}
          </div>
        </IntelligencePanel>
      )}

      <ProvenanceStrip
        source="derived"
        sourceStatus={status?.state || (status?.enabled === false ? "disabled" : "offline")}
        timestamp={status?.evaluated_at}
        license="derived"
        attribution="Derived from EMODnet, NOAA, NOAA NWS, Fintraffic Digitraffic"
        synthetic={true}
      />
    </div>
  );
}
