import { useEffect, useState } from "react";
import IntelligencePanel from "../components/maritime/primitives/IntelligencePanel.jsx";
import IntelligenceSurfaceHeader from "../components/maritime/IntelligenceSurfaceHeader.jsx";
import ProvenanceStrip from "../components/maritime/ProvenanceStrip.jsx";
import MaritimeStatusBadge from "../components/maritime/primitives/MaritimeStatusBadge.jsx";

/**
 * MaritimeResilienceView
 * ----------------------
 * Phase 3 resilience status surface. Fetches /api/maritime/source-health
 * and /api/maritime/resilience, then renders the per-source
 * snapshot tier / freshness / quality / checksum. Phase 8
 * refactored the shell to the shared primitives; the inner
 * content and the per-source data are unchanged.
 */
export default function MaritimeResilienceView() {
  const [health, setHealth] = useState(null);
  const [trafficRes, setTrafficRes] = useState(null);
  const [portRes, setPortRes] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchAll = async () => {
      try {
        const h = await fetch("/api/maritime/source-health");
        const t = await fetch("/api/maritime/resilience?dataset=emodnet_vessel_density");
        const p = await fetch("/api/maritime/resilience?dataset=noaa_ais_port_intelligence");
        if (cancelled) return;
        setHealth(h.ok ? await h.json() : null);
        setTrafficRes(t.ok ? await t.json() : null);
        setPortRes(p.ok ? await p.json() : null);
      } catch (_) {
        if (!cancelled) {
          setHealth(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchAll();
    const id = setInterval(fetchAll, 30000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex flex-col gap-4">
        <IntelligenceSurfaceHeader
          eyebrow="Operations · Maritime Resilience"
          title="Source Health & Snapshot Status"
          subtitle="Resilience core view (Phase 3). The per-source tier, freshness, and quality are reported honestly; the dashboard never upgrades an offline source to LIVE."
          overallState={health?.overall_state || (health?.enabled === false ? "disabled" : "unknown")}
          evaluatedAt={health?.evaluated_at}
        />
        <IntelligencePanel title="Loading…" density="comfortable">
          <div
            className="rounded-lg p-4 animate-pulse"
            style={{
              background: "rgba(2,12,24,0.85)",
              border: "1px solid rgba(148,163,184,0.18)",
            }}
          >
            <div className="h-3 w-32 bg-white/10 rounded mb-3" />
            <div className="h-3 w-24 bg-white/10 rounded mb-2" />
            <div className="h-3 w-20 bg-white/10 rounded" />
          </div>
        </IntelligencePanel>
      </div>
    );
  }

  return (
    <div className="p-6 flex flex-col gap-4">
      <IntelligenceSurfaceHeader
        eyebrow="Operations · Maritime Resilience"
        title="Source Health & Snapshot Status"
        subtitle="Resilience core view (Phase 3). The per-source tier, freshness, and quality are reported honestly; the dashboard never upgrades an offline source to LIVE."
        overallState={health?.overall_state || (health?.enabled === false ? "disabled" : "unknown")}
        evaluatedAt={health?.evaluated_at}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ResilienceCard
          title="EMODNET Traffic"
          enabled={health?.enabled}
          cell={health?.traffic}
          resilience={trafficRes}
        />
        <ResilienceCard
          title="NOAA Port Intelligence"
          enabled={health?.enabled}
          cell={health?.port}
          resilience={portRes}
        />
      </div>

      <div className="text-[12px] text-white/60 font-mono leading-relaxed max-w-2xl">
        Resilience core view: shows snapshot freshness, quality,
        fallback tier, and checksum status. When maritime
        intelligence is disabled (default), all cards report
        DISABLED with no network access. The pipeline, optimizer,
        and /ws/pipeline channel are untouched.
      </div>

      <ProvenanceStrip
        source="local snapshot store"
        sourceStatus={health?.overall_state || (health?.enabled === false ? "disabled" : "unknown")}
        timestamp={health?.evaluated_at}
        quality={null}
        attribution="Derived from EMODnet, NOAA MarineCadastre"
        license="Mixed open-data"
      />
    </div>
  );
}

function ResilienceCard({ title, enabled, cell, resilience }) {
  if (!enabled) {
    return (
      <IntelligencePanel title={title} density="comfortable">
        <div className="text-xs text-white/60 font-mono mt-2">DISABLED</div>
        <div className="text-[12px] text-white/60 font-mono mt-2">
          master flag off — no maritime side effects
        </div>
      </IntelligencePanel>
    );
  }
  const state = cell?.state || resilience?.state || "offline";
  const tier = cell?.tier || resilience?.tier || "empty";
  const fresh = cell?.fresh ?? resilience?.fresh ?? false;
  const recordCount = resilience?.record_count ?? cell?.record_count ?? 0;
  const quality = resilience?.quality_score ?? cell?.quality_score;
  const age = resilience?.age_seconds;
  const checksum = resilience?.checksum_records;

  return (
    <IntelligencePanel
      title={title}
      density="comfortable"
      right={<MaritimeStatusBadge value={state} pulse={fresh} />}
    >
      <dl className="mt-1 grid grid-cols-2 gap-2 text-[12px] font-mono text-white/60">
        <Field label="Snapshot" value={resilience?.snapshot_id || cell?.snapshot_id || "—"} />
        <Field label="Tier" value={tier} />
        <Field label="Records" value={String(recordCount)} />
        <Field
          label="Quality"
          value={typeof quality === "number" ? quality.toFixed(2) : "—"}
        />
        <Field
          label="Age (s)"
          value={typeof age === "number" ? age.toFixed(0) : "—"}
        />
        <Field
          label="Checksum"
          value={checksum ? checksum.slice(0, 8) + "..." : "—"}
        />
      </dl>
    </IntelligencePanel>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <dt className="uppercase tracking-widest text-white/60 text-[12px]">{label}</dt>
      <dd className="text-white/80 mt-0.5 break-all font-mono text-[12px]">{value}</dd>
    </div>
  );
}
