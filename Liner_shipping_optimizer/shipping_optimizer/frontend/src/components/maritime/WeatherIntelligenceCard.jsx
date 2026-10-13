import PulseDot from '../common/PulseDot.jsx';

/**
 * WeatherIntelligenceCard
 * -----------------------
 * Phase 5 dashboard surface for the weather intelligence layer.
 *
 * Renders: connection state, freshness, sample count, average
 * quality, license, commercial-safety flag, and attribution.
 *
 * The card NEVER claims "LIVE" on insufficient evidence. The
 * strongest claim the card will make is "AVAILABLE" when the
 * backend has materialized a snapshot within the configured
 * staleness window. Without a snapshot the card shows DISABLED
 * or OFFLINE.
 *
 * Commercial-safety is its own pill: when a provider is restricted
 * (e.g. Open-Meteo free tier), the card prominently flags the
 * snapshot as NOT COMMERCIAL-SAFE so operators cannot mistake it
 * for a production-safe source.
 */

const STATE_COLOR = {
  available: "#10b981",
  checking: "#38bdf8",
  degraded: "#f59e0b",
  stale: "#f59e0b",
  offline: "#ef4444",
  invalid: "#ef4444",
  unknown: "#64748b",
  disabled: "#64748b",
};

const STATE_LABEL = {
  available: "AVAILABLE",
  checking: "CHECKING",
  degraded: "DEGRADED",
  stale: "STALE",
  offline: "OFFLINE",
  invalid: "INVALID",
  unknown: "UNKNOWN",
  disabled: "DISABLED",
};

function formatAge(seconds) {
  if (seconds == null) return "—";
  if (seconds < 1) return "<1s ago";
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

function formatNumber(n) {
  if (n == null) return "—";
  if (typeof n === "string") return n;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export default function WeatherIntelligenceCard({ status, providers }) {
  // Disabled (feature flag off) — render a quiet placeholder.
  if (!status || status.enabled === false) {
    return (
      <div
        className="rounded-xl px-5 py-4 backdrop-blur"
        style={{
          background: "rgba(15,23,42,0.55)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <PulseDot color="#64748b" />
            <div className="text-xs font-mono text-white/40 uppercase tracking-widest">
              Weather Intelligence
            </div>
          </div>
          <div
            className="text-xs font-mono px-2 py-1 rounded"
            style={{
              background: "rgba(100,116,139,0.18)",
              color: "#94a3b8",
            }}
          >
            DISABLED
          </div>
        </div>
        <div className="text-xs text-white/30 font-mono">
          Set <code>MARITIME_WEATHER_ENABLED=1</code> and
          {" "}<code>MARITIME_WEATHER_PROVIDER</code> to opt in. The weather
          layer is OFF by default.
        </div>
      </div>
    );
  }

  const state = status.state || "unknown";
  const color = STATE_COLOR[state] || "#64748b";
  const label = STATE_LABEL[state] || state.toUpperCase();
  const commercialSafe = status.commercial_safe;
  const lic = status.license || "unresolved";
  const attr = status.attribution || "";

  return (
    <div
      className="rounded-xl px-5 py-4 backdrop-blur transition-all duration-300"
      style={{
        background: "rgba(15,23,42,0.55)",
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <PulseDot color={color} />
          <div className="text-xs font-mono text-white/40 uppercase tracking-widest">
            Weather Intelligence
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div
            className="text-xs font-mono px-2 py-1 rounded"
            style={{
              background: `${color}1a`,
              color: color,
              border: `1px solid ${color}33`,
            }}
          >
            {label}
          </div>
          {commercialSafe === false && (
            <div
              className="text-xs font-mono px-2 py-1 rounded"
              title="This provider's license is not cleared for commercial use."
              style={{
                background: "rgba(245,158,11,0.15)",
                color: "#f59e0b",
                border: "1px solid rgba(245,158,11,0.3)",
              }}
            >
              NON-COMMERCIAL
            </div>
          )}
          {commercialSafe === true && (
            <div
              className="text-xs font-mono px-2 py-1 rounded"
              style={{
                background: "rgba(16,185,129,0.12)",
                color: "#10b981",
                border: "1px solid rgba(16,185,129,0.3)",
              }}
            >
              COMMERCIAL-SAFE
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-3">
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            Provider
          </div>
          <div className="text-sm text-white/80 font-mono">
            {status.provider || "—"}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            Snapshot
          </div>
          <div className="text-sm text-white/80 font-mono truncate">
            {status.snapshot_id || "—"}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            Records
          </div>
          <div className="text-sm text-white/80 font-mono">
            {formatNumber(status.record_count)}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            Quality
          </div>
          <div className="text-sm text-white/80 font-mono">
            {status.quality_score != null
              ? Number(status.quality_score).toFixed(2)
              : "—"}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            Freshness
          </div>
          <div className="text-sm text-white/80 font-mono">
            {formatAge(status.freshness_seconds)}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            Source Health
          </div>
          <div className="text-sm text-white/80 font-mono">
            {(status.source_health || "—").toUpperCase()}
          </div>
        </div>
      </div>

      {(lic || attr) && (
        <div
          className="text-[11px] font-mono text-white/40 leading-relaxed pt-3"
          style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
        >
          {lic && (
            <div>
              <span className="text-white/30">License: </span>
              {lic}
            </div>
          )}
          {attr && (
            <div className="mt-1">
              <span className="text-white/30">Attribution: </span>
              {attr}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
