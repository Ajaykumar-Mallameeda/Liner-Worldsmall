import PulseDot from '../common/PulseDot.jsx';

/**
 * LiveMaritimeIntelligenceCard
 * ----------------------------
 * Phase 4 dashboard surface for the live maritime source. Renders
 * connection state, freshness, record count, quality, fallback state,
 * rate-limit state, and license/attribution. The card NEVER claims
 * LIVE unless the backend explicitly proves it. It is read-only.
 *
 * Status tokens (kept in lock-step with the backend):
 *   - live, cached, historical, stale, offline, degraded, disabled, error
 */

const STATE_COLOR = {
  live: "#10b981",
  cached: "#38bdf8",
  historical: "#94a3b8",
  stale: "#f59e0b",
  offline: "#ef4444",
  degraded: "#f59e0b",
  disabled: "#64748b",
  error: "#ef4444",
};

const STATE_LABEL = {
  live: "LIVE",
  cached: "CACHED",
  historical: "HISTORICAL",
  stale: "STALE",
  offline: "OFFLINE",
  degraded: "DEGRADED",
  disabled: "DISABLED",
  error: "ERROR",
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

export default function LiveMaritimeIntelligenceCard({ status, providers }) {
  // Disabled (feature flag off) — render a quiet placeholder.
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
          <div className="text-xs uppercase tracking-widest text-white/40 font-mono">
            Live Maritime Intelligence
          </div>
          <span className="text-[10px] font-mono text-white/30 uppercase">Disabled</span>
        </div>
        <div className="text-[11px] text-white/30 font-mono">
          Set <span className="text-white/50">MARITIME_LIVE_ENABLED=1</span> and
          <span className="text-white/50"> MARITIME_LIVE_PROVIDER=digitraffic</span>{" "}
          to enable. Default is OFF. The optimizer never makes a network call.
        </div>
      </div>
    );
  }

  const state = (status.state || "offline").toLowerCase();
  const color = STATE_COLOR[state] || STATE_COLOR.offline;
  const label = STATE_LABEL[state] || "OFFLINE";
  const provider = (status.provider || providers?.[0]?.name || "—").toString();
  const rateLimited = Boolean(status.rate_limited);
  const fresh = state === "live";
  const attribution = status.attribution || "";

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
        <div className="text-xs uppercase tracking-widest text-white/40 font-mono">
          Live Maritime Intelligence
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

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] font-mono">
        <div className="text-white/40">Provider</div>
        <div className="text-white/80 text-right">
          {provider === "digitraffic" ? "Digitraffic" : provider}
        </div>

        <div className="text-white/40">Last update</div>
        <div className="text-white/80 text-right">
          {formatAge(status.freshness_seconds)}
        </div>

        <div className="text-white/40">Records</div>
        <div className="text-white/80 text-right">
          {formatNumber(status.record_count)}
        </div>

        <div className="text-white/40">Quality</div>
        <div className="text-white/80 text-right">
          {status.quality_score != null
            ? Number(status.quality_score).toFixed(2)
            : "—"}
        </div>

        <div className="text-white/40">Fallback</div>
        <div className="text-white/80 text-right">
          {status.fallback_tier || "—"}
        </div>

        <div className="text-white/40">Rate-limit</div>
        <div
          className="text-right"
          style={{ color: rateLimited ? "#f59e0b" : "rgba(255,255,255,0.8)" }}
        >
          {rateLimited ? "RATE LIMITED" : "OK"}
        </div>

        <div className="text-white/40">Snapshot</div>
        <div
          className="text-white/60 text-right truncate"
          title={status.snapshot_id || ""}
        >
          {status.snapshot_id || "—"}
        </div>

        <div className="text-white/40">License</div>
        <div className="text-white/80 text-right">{status.license || "unresolved"}</div>
      </div>

      {!fresh && (
        <div
          className="mt-2 pt-2 border-t border-white/5 text-[11px] font-mono"
          style={{ color: "#f59e0b" }}
        >
          {state === "stale"
            ? "Snapshot is older than MARITIME_LIVE_MAX_AGE_SECONDS. Showing last good live."
            : state === "cached"
              ? "Live feed unavailable. Serving the most recent valid live snapshot."
              : state === "historical"
                ? "No valid live snapshot. Falling back to the historical reference dataset."
                : "Live source is unreachable. No live data is being shown."}
        </div>
      )}

      {attribution && (
        <div className="mt-2 pt-2 border-t border-white/5 text-[10px] text-white/30 font-mono leading-tight">
          {attribution}
        </div>
      )}

      {status.error && (
        <div className="mt-1 text-[10px] text-white/40 font-mono">
          Last error: {String(status.error_kind || "—")} · {String(status.error).slice(0, 80)}
        </div>
      )}
    </div>
  );
}
