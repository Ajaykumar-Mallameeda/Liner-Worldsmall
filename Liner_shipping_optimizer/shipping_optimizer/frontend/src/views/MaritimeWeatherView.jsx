import { useEffect, useState } from "react";
import WeatherIntelligenceCard from "../components/maritime/WeatherIntelligenceCard.jsx";
import IntelligencePanel from "../components/maritime/primitives/IntelligencePanel.jsx";
import IntelligenceSurfaceHeader from "../components/maritime/IntelligenceSurfaceHeader.jsx";
import ProvenanceStrip from "../components/maritime/ProvenanceStrip.jsx";
import ProviderStatusRow from "../components/maritime/primitives/ProviderStatusRow.jsx";
import OperationalTable from "../components/maritime/primitives/OperationalTable.jsx";

/**
 * MaritimeWeatherView
 * -------------------
 * Phase 5 weather intelligence surface. Polls
 *   - /api/maritime/weather/status
 *   - /api/maritime/weather/snapshot
 *   - /api/maritime/weather/providers
 *   - /api/maritime/weather/forecast
 * and exposes on-demand queries to /weather/at and /weather/route.
 * Phase 8 swapped the ad-hoc glass divs for IntelligencePanel,
 * the records preview for OperationalTable, and the provider
 * rows for ProviderStatusRow.
 */
export default function MaritimeWeatherView() {
  const [status, setStatus] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [providers, setProviders] = useState([]);
  const [atQuery, setAtQuery] = useState({ lat: 53.55, lon: 9.99, radius_km: 250.0 });
  const [atResult, setAtResult] = useState(null);
  const [forecastResult, setForecastResult] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchAll = async () => {
      try {
        const [sResp, snapResp, provResp, fResp] = await Promise.all([
          fetch("/api/maritime/weather/status").catch(() => null),
          fetch("/api/maritime/weather/snapshot").catch(() => null),
          fetch("/api/maritime/weather/providers").catch(() => null),
          fetch("/api/maritime/weather/forecast?limit=16").catch(() => null),
        ]);
        if (cancelled) return;
        if (sResp && sResp.ok) setStatus(await sResp.json());
        if (snapResp && snapResp.ok) setSnapshot(await snapResp.json());
        if (provResp && provResp.ok) {
          const j = await provResp.json();
          setProviders(j.providers || []);
        }
        if (fResp && fResp.ok) setForecastResult(await fResp.json());
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

  const runAt = async () => {
    try {
      const u =
        `/api/maritime/weather/at?lat=${atQuery.lat}&lon=${atQuery.lon}` +
        `&radius_km=${atQuery.radius_km}&limit=8`;
      const r = await fetch(u);
      if (r.ok) setAtResult(await r.json());
    } catch (_) {
      setAtResult({ ok: false, records: [], error: "request_failed" });
    }
  };

  return (
    <div className="space-y-5 p-6">
      <IntelligenceSurfaceHeader
        eyebrow="Operations · Weather Intelligence"
        title="Weather Intelligence"
        subtitle="Phase 5 weather layer. Snapshot-only by design; never claims LIVE on insufficient evidence."
        overallState={status?.state || (status?.enabled === false ? "disabled" : "unknown")}
        evaluatedAt={status?.retrieved_at || snapshot?.retrieved_at}
        right={
          <span
            className="mono-data"
            style={{
              fontSize: 9,
              color: 'var(--maritime-ink-faint)',
              textTransform: 'uppercase',
              letterSpacing: '0.18em',
            }}
          >
            {status?.commercial_safe === false
              ? "non-commercial"
              : status?.commercial_safe
                ? "commercial-safe"
                : "license n/a"}
          </span>
        }
      />

      <WeatherIntelligenceCard status={status} providers={providers} />

      <div className="grid grid-cols-3 gap-4">
        {/* Provider catalog */}
        <IntelligencePanel
          title="Providers"
          density="comfortable"
        >
          <div className="flex flex-col gap-3">
            {(providers || []).map((p) => (
              <ProviderStatusRow
                key={p.name}
                name={p.name}
                label={p.label || p.name}
                status={p.commercial_safe ? "available" : "degraded"}
                license={p.license}
                coverage={p.coverage}
                commercialSafe={p.commercial_safe}
                url={p.endpoint}
              />
            ))}
            {!providers.length && (
              <div className="text-[11px] font-mono text-white/30">
                No providers registered.
              </div>
            )}
          </div>
        </IntelligencePanel>

        {/* At-coord query */}
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
                    {(r.latitude ?? "?").toFixed(2)}, {(r.longitude ?? "?").toFixed(2)} —{" "}
                    {r.valid_at || "?"}
                  </div>
                  <div>
                    wind {r.wind_speed_ms != null ? r.wind_speed_ms.toFixed(1) : "—"} m/s
                    {" · "}wave {r.wave_height_m != null ? r.wave_height_m.toFixed(2) : "—"} m
                    {" · "}q {r.quality != null ? r.quality.toFixed(2) : "—"}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-[11px] font-mono text-white/30">
                {atResult ? "No observations near this coordinate." : "Run a query to see results."}
              </div>
            )}
          </div>
        </IntelligencePanel>

        {/* Forecast window preview */}
        <IntelligencePanel
          title="Forecast Window"
          density="comfortable"
        >
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {forecastResult && forecastResult.records && forecastResult.records.length > 0 ? (
              forecastResult.records.map((r, i) => (
                <div
                  key={i}
                  className="text-[11px] font-mono text-white/60 py-1"
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                >
                  <div className="text-white/40">
                    {r.valid_at || "?"} — {(r.latitude ?? "?").toFixed(2)},{(r.longitude ?? "?").toFixed(2)}
                  </div>
                  <div>
                    wind {r.wind_speed_ms != null ? r.wind_speed_ms.toFixed(1) : "—"} m/s
                    {" · "}gust {r.gust_speed_ms != null ? r.gust_speed_ms.toFixed(1) : "—"} m/s
                    {" · "}wave {r.wave_height_m != null ? r.wave_height_m.toFixed(2) : "—"} m
                  </div>
                </div>
              ))
            ) : (
              <div className="text-[11px] font-mono text-white/30">
                No forecast records in window.
              </div>
            )}
          </div>
        </IntelligencePanel>
      </div>

      {/* Snapshot preview */}
      {snapshot && snapshot.available && (
        <IntelligencePanel
          title="Records Preview (first 50)"
          density="compact"
        >
          <OperationalTable
            columns={[
              { key: "valid_at", label: "valid_at" },
              {
                key: "lat",
                label: "lat",
                render: (r) =>
                  r.latitude != null ? r.latitude.toFixed(2) : "—",
              },
              {
                key: "lon",
                label: "lon",
                render: (r) =>
                  r.longitude != null ? r.longitude.toFixed(2) : "—",
              },
              {
                key: "wind",
                label: "wind (m/s)",
                align: "right",
                render: (r) =>
                  r.wind_speed_ms != null
                    ? r.wind_speed_ms.toFixed(1)
                    : "—",
              },
              {
                key: "gust",
                label: "gust (m/s)",
                align: "right",
                render: (r) =>
                  r.gust_speed_ms != null
                    ? r.gust_speed_ms.toFixed(1)
                    : "—",
              },
              {
                key: "wave",
                label: "wave (m)",
                align: "right",
                render: (r) =>
                  r.wave_height_m != null
                    ? r.wave_height_m.toFixed(2)
                    : "—",
              },
              {
                key: "pressure",
                label: "pressure (hPa)",
                align: "right",
                render: (r) =>
                  r.pressure_hpa != null
                    ? r.pressure_hpa.toFixed(1)
                    : "—",
              },
              {
                key: "quality",
                label: "q",
                align: "right",
                render: (r) =>
                  r.quality != null ? r.quality.toFixed(2) : "—",
              },
            ]}
            rows={(snapshot.records || []).slice(0, 50)}
            rowKey="valid_at"
            density="compact"
            maxHeight={320}
          />
        </IntelligencePanel>
      )}

      <ProvenanceStrip
        source={status?.provider || "Weather"}
        sourceStatus={status?.state || "unknown"}
        timestamp={status?.retrieved_at || snapshot?.retrieved_at}
        quality={status?.quality}
        license={status?.license}
        attribution={status?.attribution}
        recordCount={status?.record_count}
        snapshotId={status?.snapshot_id}
      />
    </div>
  );
}
