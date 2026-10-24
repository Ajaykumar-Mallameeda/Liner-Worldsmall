import { useEffect, useState } from "react";
import IntelligencePanel from "../components/maritime/primitives/IntelligencePanel.jsx";
import IntelligenceSurfaceHeader from "../components/maritime/IntelligenceSurfaceHeader.jsx";
import ProvenanceStrip from "../components/maritime/ProvenanceStrip.jsx";
import SourceHealthIndicator from "../components/maritime/primitives/SourceHealthIndicator.jsx";
import MaritimeStatusBadge from "../components/maritime/primitives/MaritimeStatusBadge.jsx";

/**
 * MaritimeOpsView
 * ---------------
 * Phase 2 port-intelligence console. Polls
 *   - /api/maritime/sources
 *   - /api/maritime/ports
 *   - /api/maritime/port-calls
 *   - /api/maritime/snapshot?kind=port
 * Phase 8 swapped the ad-hoc shell for the shared primitives;
 * the data plumbing and the per-port rows are unchanged.
 */

const POLL_INTERVAL_MS = 30000;

function Skeleton({ height = "h-20" }) {
  return (
    <div
      className={`animate-pulse rounded ${height}`}
      style={{ background: "rgba(148,163,184,0.08)" }}
    />
  );
}

function EmptyState({ message }) {
  return (
    <div className="text-[12px] text-white/60 font-mono leading-relaxed py-4 text-center">
      {message}
    </div>
  );
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return iso.replace("T", " ").replace("Z", " UTC").slice(0, 19);
  } catch {
    return iso;
  }
}

function fmtMinutes(m) {
  if (m == null) return "—";
  if (m < 60) return `${m.toFixed(0)}m`;
  return `${(m / 60).toFixed(1)}h`;
}

export default function MaritimeOpsView() {
  const [enabled, setEnabled] = useState(null);
  const [sources, setSources] = useState([]);
  const [ports, setPorts] = useState([]);
  const [activity, setActivity] = useState([]);
  const [mix, setMix] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [snapshot, setSnapshot] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [sourcesResp, portsResp, callsResp, snapResp] = await Promise.all([
          fetch("/api/maritime/sources").then((r) => (r.ok ? r.json() : null)),
          fetch("/api/maritime/ports").then((r) => (r.ok ? r.json() : null)),
          fetch("/api/maritime/port-calls?limit=200").then((r) =>
            r.ok ? r.json() : null,
          ),
          fetch("/api/maritime/snapshot?kind=port").then((r) =>
            r.ok ? r.json() : null,
          ),
        ]);
        if (cancelled) return;
        if (sourcesResp) {
          setEnabled(sourcesResp.enabled ?? false);
          setSources(sourcesResp.sources || []);
        } else {
          setEnabled(false);
        }
        if (portsResp) setPorts(portsResp.ports || []);
        if (callsResp) setTimeline(callsResp.port_calls || []);
        if (snapResp) setSnapshot(snapResp);
      } catch (_) {
        if (!cancelled) setEnabled(false);
      }
    };
    load();
    const t = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    if (!snapshot || !snapshot.metadata) {
      setActivity([]);
      setMix([]);
      return;
    }
    const sid = snapshot.metadata.snapshot_id;
    if (!sid) return;
    fetch(`/api/maritime/snapshot?kind=port`)
      .then((r) => (r.ok ? r.json() : null))
      .then(async (data) => {
        if (!data || !data.metadata || !data.metadata.snapshot_id) return;
        const portIds = (ports || []).map((p) => p.port_id);
        const results = await Promise.all(
          portIds.map((pid) =>
            fetch(`/api/maritime/ports/${pid}`).then((r) =>
              r.ok ? r.json() : null,
            ),
          ),
        );
        const act = [];
        const mixF = [];
        for (const r of results) {
          if (!r || !r.enabled) continue;
          if (r.activity) act.push(r.activity);
          if (r.vessel_type_mix) mixF.push(r.vessel_type_mix);
        }
        setActivity(act);
        setMix(mixF);
      })
      .catch(() => {});
  }, [snapshot, ports]);

  if (enabled === null) {
    return (
      <div className="p-6 flex flex-col gap-4">
        <IntelligenceSurfaceHeader
          eyebrow="Operations · Maritime Intelligence"
          title="Port Intelligence Console"
          subtitle="Phase 2 NOAA MarineCadastre port intelligence."
          overallState="unknown"
        />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      </div>
    );
  }

  if (!enabled) {
    return (
      <div className="p-6 flex flex-col gap-4">
        <IntelligenceSurfaceHeader
          eyebrow="Operations · Maritime Intelligence"
          title="Port Intelligence Console"
          subtitle="Phase 2 NOAA MarineCadastre port intelligence."
          overallState="unknown"
        />
        <IntelligencePanel
          title="Status"
          right={<MaritimeStatusBadge value="disabled" />}
        >
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-mono text-white/60">
              Maritime intelligence
            </span>
          </div>
          <div className="text-[12px] text-white/60 font-mono mt-2">
            Set MARITIME_INTELLIGENCE_ENABLED=1 to enable port
            intelligence.
          </div>
        </IntelligencePanel>
      </div>
    );
  }

  const portCalls = snapshot?.metadata?.call_count ?? timeline.length;

  return (
    <div className="p-6 flex flex-col gap-4">
      <IntelligenceSurfaceHeader
        eyebrow="Operations · Maritime Intelligence"
        title="Port Intelligence Console"
        subtitle="Phase 2 NOAA MarineCadastre port intelligence. Each row is read from the local snapshot store; missing data renders as —, never fabricated."
        overallState={enabled ? (snapshot?.metadata?.state || "available") : "disabled"}
        evaluatedAt={snapshot?.metadata?.evaluated_at}
      />

      {/* Source health */}
      <IntelligencePanel
        title="Source Health"
        density="compact"
      >
        <div className="flex flex-col gap-2">
          {sources.map((s) => (
            <SourceHealthIndicator
              key={s.source}
              source={s.source}
              dataset={s.dataset}
              state={s.source_status || s.quality_status || "unknown"}
              license={s.license}
              recordCount={s.record_count}
              snapshotId={s.snapshot_id}
              attribution={s.attribution}
            />
          ))}
          {sources.length === 0 && (
            <EmptyState message="No maritime sources available." />
          )}
        </div>
      </IntelligencePanel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Port activity */}
        <IntelligencePanel title="Port Activity" density="compact">
          {activity.length === 0 ? (
            <EmptyState message="No port activity available." />
          ) : (
            <div className="flex flex-col gap-2">
              {activity.map((a) => (
                <div
                  key={a.port_id}
                  className="rounded p-2"
                  style={{
                    background: "rgba(15,23,42,0.6)",
                    border: "1px solid rgba(148,163,184,0.10)",
                  }}
                >
                  <div className="flex items-center justify-between text-[12px] font-mono">
                    <span className="text-white/80">
                      {a.port_name || a.port_id}
                    </span>
                    <span className="text-white/60">
                      {a.call_count} calls
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-x-3 mt-1 text-[12px] font-mono">
                    <div>
                      <div className="text-white/60">Confirmed</div>
                      <div className="text-white/70">{a.confirmed_count}</div>
                    </div>
                    <div>
                      <div className="text-white/60">Open</div>
                      <div className="text-white/70">{a.open_count}</div>
                    </div>
                    <div>
                      <div className="text-white/60">Rejected</div>
                      <div className="text-white/70">{a.rejected_count}</div>
                    </div>
                    <div className="col-span-3 mt-1 text-white/60">
                      Avg dwell {fmtMinutes(a.avg_dwell_minutes)} ·{" "}
                      {a.unique_vessels} unique vessels
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </IntelligencePanel>

        {/* Vessel-type mix */}
        <IntelligencePanel title="Vessel-Type Mix" density="compact">
          {mix.length === 0 ? (
            <EmptyState message="No vessel-type mix available." />
          ) : (
            <div className="flex flex-col gap-2">
              {mix.map((m) => (
                <div
                  key={m.port_id}
                  className="rounded p-2"
                  style={{
                    background: "rgba(15,23,42,0.6)",
                    border: "1px solid rgba(148,163,184,0.10)",
                  }}
                >
                  <div className="flex items-center justify-between text-[12px] font-mono">
                    <span className="text-white/80">
                      {m.port_name || m.port_id}
                    </span>
                    <span className="text-white/60 text-[12px]">
                      dominant: {m.dominant_type}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {Object.entries(m.counts_by_type || {}).map(
                      ([type, count]) => (
                        <span
                          key={type}
                          className="text-[12px] font-mono px-1.5 py-0.5 rounded"
                          style={{
                            background: "rgba(148,163,184,0.10)",
                            color: "rgba(255,255,255,0.65)",
                          }}
                        >
                          {type} · {count}
                        </span>
                      ),
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </IntelligencePanel>
      </div>

      {/* Port-call timeline */}
      <IntelligencePanel
        title={`Port-Call Timeline (${timeline.length} of ${portCalls})`}
        density="compact"
      >
        {timeline.length === 0 ? (
          <EmptyState message="No port-calls recorded." />
        ) : (
          <div
            className="flex flex-col gap-1 max-h-72 overflow-y-auto"
            style={{ scrollbarWidth: "thin" }}
          >
            {timeline.map((c) => (
              <div
                key={c.port_call_id}
                className="grid grid-cols-12 gap-2 text-[12px] font-mono py-1"
                style={{
                  borderBottom: "1px solid rgba(148,163,184,0.08)",
                }}
              >
                <div className="col-span-2 text-white/60">
                  {fmtTime(c.arrival_ts)}
                </div>
                <div className="col-span-3 text-white/70 truncate">
                  {c.port_id}
                </div>
                <div className="col-span-3 text-white/70 truncate">
                  {c.mmsi}
                </div>
                <div className="col-span-2 text-white/60 truncate">
                  {c.vessel_type}
                </div>
                <div className="col-span-2 text-right text-white/50">
                  {fmtMinutes(c.dwell_minutes)} · {c.status}
                </div>
              </div>
            ))}
          </div>
        )}
      </IntelligencePanel>

      {/* Snapshot / provenance */}
      {snapshot?.metadata && (
        <IntelligencePanel
          title="Snapshot Provenance"
          density="compact"
        >
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[12px] font-mono">
            <div className="text-white/60">Source</div>
            <div className="text-white/80 text-right">
              {snapshot.metadata.source || "—"}
            </div>
            <div className="text-white/60">Dataset</div>
            <div className="text-white/80 text-right">
              {snapshot.metadata.dataset || "—"}
            </div>
            <div className="text-white/60">Version</div>
            <div className="text-white/80 text-right">
              {snapshot.metadata.dataset_version || "—"}
            </div>
            <div className="text-white/60">License</div>
            <div className="text-white/80 text-right">
              {snapshot.metadata.license || "—"}
            </div>
            <div className="text-white/60">Quality</div>
            <div className="text-white/80 text-right">
              {typeof snapshot.metadata.quality_score === "number"
                ? snapshot.metadata.quality_score.toFixed(2)
                : "—"}
            </div>
            <div className="text-white/60">Snapshot ID</div>
            <div className="text-white/60 text-right truncate">
              {snapshot.metadata.snapshot_id || "—"}
            </div>
            {snapshot.metadata.attribution && (
              <div className="text-white/60 col-span-2 mt-2 pt-2 border-t border-white/5 text-[12px]">
                {snapshot.metadata.attribution}
              </div>
            )}
          </div>
        </IntelligencePanel>
      )}

      <div className="text-[12px] text-white/60 font-mono leading-relaxed max-w-2xl">
        Phase 2 port-intelligence console. All values are derived from
        the local NOAA MarineCadastre snapshot on disk; no network
        calls are made from the dashboard. Polled every{" "}
        {POLL_INTERVAL_MS / 1000}s.
      </div>

      <ProvenanceStrip
        source="NOAA MarineCadastre"
        sourceStatus={enabled ? (snapshot?.metadata?.state || "available") : "disabled"}
        timestamp={snapshot?.metadata?.evaluated_at}
        license="CC0 (US Government public domain)"
        attribution="NOAA MarineCadastre — historical AIS / port-call data"
        recordCount={snapshot?.metadata?.call_count}
        snapshotId={snapshot?.metadata?.snapshot_id}
      />
    </div>
  );
}
