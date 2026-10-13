import { useEffect, useState } from "react";
import LiveMaritimeIntelligenceCard from "../components/maritime/LiveMaritimeIntelligenceCard.jsx";
import IntelligencePanel from "../components/maritime/primitives/IntelligencePanel.jsx";
import IntelligenceSurfaceHeader from "../components/maritime/IntelligenceSurfaceHeader.jsx";
import ProvenanceStrip from "../components/maritime/ProvenanceStrip.jsx";
import ProviderStatusRow from "../components/maritime/primitives/ProviderStatusRow.jsx";

/**
 * MaritimeLiveView
 * ----------------
 * Phase 4 live maritime intelligence surface. Polls
 *   - /api/maritime/live/status
 *   - /api/maritime/live/snapshot
 *   - /api/maritime/live/providers
 * Phase 8 refactored the shell to use the shared primitives;
 * the inner card and the provider rows now use the
 * ProviderStatusRow primitive.
 */
export default function MaritimeLiveView() {
  const [status, setStatus] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchAll = async () => {
      try {
        const [sResp, snapResp, provResp] = await Promise.all([
          fetch("/api/maritime/live/status").catch(() => null),
          fetch("/api/maritime/live/snapshot").catch(() => null),
          fetch("/api/maritime/live/providers").catch(() => null),
        ]);
        if (cancelled) return;
        if (sResp && sResp.ok) setStatus(await sResp.json());
        if (snapResp && snapResp.ok) setSnapshot(await snapResp.json());
        if (provResp && provResp.ok) {
          const j = await provResp.json();
          setProviders(j.providers || []);
        }
      } catch (_) {
        if (!cancelled) {
          setStatus({ enabled: false });
        }
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

  return (
    <div className="p-6 flex flex-col gap-4">
      <IntelligenceSurfaceHeader
        eyebrow="Operations · Live Maritime Intelligence"
        title="Live Source Status"
        subtitle="Phase 4 live maritime intelligence. The live layer is enabled but currently reports OFFLINE because no live snapshot is on disk — the dashboard does not fabricate live vessel positions."
        overallState={status?.state || (status?.enabled === false ? "disabled" : "offline")}
        evaluatedAt={status?.evaluated_at}
      />

      <IntelligencePanel
        title="Live connection"
        density="comfortable"
      >
        {loading ? (
          <div
            className="rounded-lg p-3 animate-pulse"
            style={{
              background: "rgba(2,12,24,0.85)",
              border: "1px solid rgba(148,163,184,0.18)",
            }}
          >
            <div className="h-3 w-40 bg-white/10 rounded mb-3" />
            <div className="h-3 w-32 bg-white/10 rounded mb-2" />
            <div className="h-3 w-24 bg-white/10 rounded" />
          </div>
        ) : (
          <LiveMaritimeIntelligenceCard status={status} providers={providers} />
        )}
      </IntelligencePanel>

      {providers && providers.length > 0 && (
        <IntelligencePanel
          title="Registered providers"
          density="compact"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {providers.map((p) => (
              <ProviderStatusRow
                key={p.name}
                name={p.name}
                label={p.label || p.name}
                status={p.status || "unknown"}
                license={p.license}
                coverage={p.coverage}
                commercialSafe={p.commercial_safe}
                url={p.endpoint}
              />
            ))}
          </div>
        </IntelligencePanel>
      )}

      {snapshot && snapshot.metadata && (
        <IntelligencePanel
          title="Latest snapshot"
          density="compact"
        >
          <div className="text-[11px] font-mono text-white/60 grid grid-cols-2 gap-x-4 gap-y-1">
            <div className="text-white/40">snapshot_id</div>
            <div className="text-white/80 text-right">{snapshot.metadata.snapshot_id || "—"}</div>
            <div className="text-white/40">source</div>
            <div className="text-white/80 text-right">{snapshot.metadata.source || "—"}</div>
            <div className="text-white/40">records</div>
            <div className="text-white/80 text-right">{snapshot.metadata.accepted_records ?? 0}</div>
            <div className="text-white/40">created_at</div>
            <div className="text-white/80 text-right">{snapshot.metadata.created_at || "—"}</div>
          </div>
        </IntelligencePanel>
      )}

      <div className="text-[11px] text-white/30 font-mono leading-relaxed max-w-2xl">
        Phase 4 surface for the live maritime ingestion layer. The
        optimizer never makes a network call: live data becomes an
        immutable local snapshot before the rest of the system can see
        it. The default state is <span className="text-white/50">disabled</span>;
        live ingestion is double-gated by
        <span className="text-white/50"> MARITIME_LIVE_ENABLED</span> and
        <span className="text-white/50"> MARITIME_LIVE_PROVIDER</span>.
        The card never claims LIVE unless the source-health state
        explicitly proves it.
      </div>

      <ProvenanceStrip
        source={providers?.[0]?.name || "Live"}
        sourceStatus={status?.state || (status?.enabled === false ? "disabled" : "offline")}
        timestamp={status?.evaluated_at}
        quality={status?.quality}
        license={providers?.[0]?.license}
        attribution={providers?.[0]?.attribution}
        snapshotId={status?.snapshot_id || snapshot?.metadata?.snapshot_id}
      />
    </div>
  );
}
