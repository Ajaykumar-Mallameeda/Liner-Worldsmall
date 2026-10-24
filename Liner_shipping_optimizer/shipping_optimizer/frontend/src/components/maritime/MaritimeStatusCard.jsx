import PulseDot from '../common/PulseDot.jsx';

/**
 * MaritimeStatusCard
 * ------------------
 * Phase 1 dashboard foundation. Shows the maritime data source status
 * (EMODnet traffic). Designed to slot into the existing Overview tab
 * alongside the other status widgets. Does not redesign the dashboard.
 *
 * Status is determined by the props passed in by the parent; the parent
 * is responsible for fetching /api/maritime/status and passing the
 * result. When the parent is absent (legacy callers) the card renders
 * a benign "Maritime intelligence: OFF" placeholder.
 */

const STATUS_COLOR = {
  healthy: "#10b981",
  available: "#10b981",
  degraded: "#f59e0b",
  stale: "#f59e0b",
  invalid: "#ef4444",
  offline: "#ef4444",
  unknown: "#94a3b8",
  disabled: "#64748b",
};

const STATUS_LABEL = {
  healthy: "HEALTHY",
  available: "AVAILABLE",
  degraded: "DEGRADED",
  stale: "STALE",
  invalid: "INVALID",
  offline: "OFFLINE",
  unknown: "UNKNOWN",
  disabled: "DISABLED",
};

export default function MaritimeStatusCard({ status, snapshot }) {
  // Disabled (feature flag off) — show a quiet placeholder, no spinner.
  if (!status || status.enabled === false) {
    return (
      <div
        className="rounded-lg p-3 transition-colors duration-300"
        style={{
          background: "rgba(15,23,42,0.6)",
          border: "1px solid rgba(148,163,184,0.18)",
        }}
      >
        <div className="flex items-center justify-between mb-1">
          <div className="text-xs uppercase tracking-widest text-white/60 font-mono">
            Maritime Intelligence
          </div>
          <span className="text-[12px] font-mono text-white/60 uppercase">Disabled</span>
        </div>
        <div className="text-[12px] text-white/60 font-mono">
          No maritime sources active. Set MARITIME_INTELLIGENCE_ENABLED=1 to enable.
        </div>
      </div>
    );
  }

  const qualityKey = (status.quality_status || "unknown").toLowerCase();
  const sourceKey = (status.source_status || "unknown").toLowerCase();
  const color = STATUS_COLOR[sourceKey] || STATUS_COLOR[qualityKey] || STATUS_COLOR.unknown;
  const label = STATUS_LABEL[sourceKey] || STATUS_LABEL[qualityKey] || "UNKNOWN";

  return (
    <div
      className="rounded-lg p-3 transition-colors duration-300"
      style={{
        background: "rgba(2,12,24,0.85)",
        border: `1px solid ${color}33`,
        backdropFilter: "blur(20px)",
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs uppercase tracking-widest text-white/60 font-mono">
          Maritime Intelligence
        </div>
        <div className="flex items-center gap-2">
          <PulseDot color={color} />
          <span
            className="text-xs font-mono uppercase tracking-widest"
            style={{ color }}
          >
            {label}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[12px] font-mono">
        <div className="text-white/60">Traffic</div>
        <div className="text-white/80 text-right">
          {status.traffic_available ? "AVAILABLE" : "—"}
        </div>

        <div className="text-white/60">Source</div>
        <div className="text-white/80 text-right">{status.source || "—"}</div>

        <div className="text-white/60">Coverage</div>
        <div className="text-white/80 text-right">
          {status.record_count != null ? `${status.record_count} cells` : "—"}
        </div>

        <div className="text-white/60">Freshness</div>
        <div className="text-white/80 text-right">{status.freshness_label || "Historical"}</div>

        <div className="text-white/60">Quality</div>
        <div className="text-white/80 text-right">
          {status.quality_score != null ? status.quality_score.toFixed(2) : "—"}
        </div>

        <div className="text-white/60">Snapshot</div>
        <div className="text-white/60 text-right truncate" title={status.snapshot_id || ""}>
          {status.snapshot_id || "—"}
        </div>
      </div>

      {snapshot && snapshot.attribution && (
        <div className="mt-2 pt-2 border-t border-white/5 text-[12px] text-white/60 font-mono leading-tight">
          {snapshot.attribution}
        </div>
      )}
    </div>
  );
}
