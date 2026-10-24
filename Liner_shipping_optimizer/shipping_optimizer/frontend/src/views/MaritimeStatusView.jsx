import { useEffect, useState } from "react";
import MaritimeStatusCard from "../components/maritime/MaritimeStatusCard.jsx";
import IntelligencePanel from "../components/maritime/primitives/IntelligencePanel.jsx";
import IntelligenceSurfaceHeader from "../components/maritime/IntelligenceSurfaceHeader.jsx";
import ProvenanceStrip from "../components/maritime/ProvenanceStrip.jsx";
import OperationalEmptyState from "../components/maritime/OperationalEmptyState.jsx";

/**
 * MaritimeStatusView
 * ------------------
 * Phase 1 maritime status surface. Polls /api/maritime/status and
 * /api/maritime/snapshot (best-effort). Phase 8 refactored the
 * shell to use the shared MaritimeSectionHeader +
 * IntelligencePanel primitives; Phase 10 lifted the surface to
 * use the new shared IntelligenceSurfaceHeader +
 * ProvenanceStrip + OperationalEmptyState primitives for cross-view
 * visual coherence.
 */
export default function MaritimeStatusView() {
  const [status, setStatus] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const resp = await fetch("/api/maritime/status");
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (cancelled) return;
        setStatus(data);
        try {
          const snapResp = await fetch("/api/maritime/snapshot");
          if (snapResp.ok) setSnapshot(await snapResp.json());
        } catch (_) {
          // best-effort
        }
      } catch (_) {
        if (!cancelled) {
          setStatus({ enabled: false, traffic_available: false });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchStatus();
    const t = setInterval(fetchStatus, 30000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  const isDisabled = !status || status.enabled === false;
  const overallState = isDisabled
    ? "disabled"
    : status?.source_status || (status?.traffic_available ? "available" : "offline");
  const evaluatedAt = status?.evaluated_at || status?.retrieved_at || null;

  return (
    <div className="p-6 flex flex-col gap-5">
      <IntelligenceSurfaceHeader
        eyebrow="Operations · Maritime Intelligence"
        title="Data Source Status"
        subtitle="Phase 1 EMODnet vessel-density status panel. Each row reports its own state honestly; the dashboard never upgrades an offline source to LIVE."
        overallState={overallState}
        evaluatedAt={evaluatedAt}
      />

      <IntelligencePanel
        title="EMODNET"
        density="comfortable"
      >
        {loading ? (
          <OperationalEmptyState variant="loading" statusBadge={false} />
        ) : status && status.traffic_available === false && isDisabled === false ? (
          <OperationalEmptyState
            variant="offline"
            title="EMODNET snapshot is offline"
            hint="The source layer is enabled but no snapshot is on disk. The dashboard keeps reading the local snapshot store and will surface real data as soon as the orchestrator publishes one."
          />
        ) : (
          <MaritimeStatusCard status={status} snapshot={snapshot} />
        )}
      </IntelligencePanel>

      <ProvenanceStrip
        source={status?.source || "EMODNET"}
        sourceStatus={overallState}
        timestamp={evaluatedAt}
        quality={
          status && status.quality_score != null
            ? Number(status.quality_score).toFixed(2)
            : null
        }
        license={status?.license}
        attribution={status?.attribution}
        snapshotId={status?.snapshot_id}
        recordCount={status?.record_count}
      />

      <div className="text-[12px] text-white/60 font-mono leading-relaxed max-w-2xl">
        This panel is the Phase 1 maritime operations surface. It shows
        the status of the EMODnet vessel-density data source. When
        maritime intelligence is disabled (default), the panel reports
        DISABLED with no network access. When enabled, the panel shows
        freshness, record count, and quality. No pipeline state is
        mutated.
      </div>
    </div>
  );
}
