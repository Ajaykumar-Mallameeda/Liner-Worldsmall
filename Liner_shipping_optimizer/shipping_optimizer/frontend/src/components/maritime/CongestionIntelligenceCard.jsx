import PulseDot from '../common/PulseDot.jsx';

/**
 * CongestionIntelligenceCard
 * --------------------------
 * Phase 6 dashboard surface for the congestion intelligence layer.
 *
 * Renders: state, freshness, record count, quality, synthetic
 * label, and an at-a-glance explainability strip (traffic /
 * port / weather contributions).
 *
 * The card NEVER claims "LIVE" on insufficient evidence. The
 * strongest claim is "AVAILABLE" when a snapshot is present and
 * fresh. Synthetic data is clearly labelled so the operator
 * cannot mistake it for real-world congestion.
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

const LEVEL_COLOR = {
  low: "#10b981",
  moderate: "#38bdf8",
  high: "#f59e0b",
  severe: "#ef4444",
};

const LEVEL_LABEL = {
  low: "LOW",
  moderate: "MODERATE",
  high: "HIGH",
  severe: "SEVERE",
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

function Bar({ value, color = "#00d4ff" }) {
  const v = Math.max(0, Math.min(1, Number(value) || 0));
  return (
    <div
      className="w-full h-1.5 rounded"
      style={{ background: "rgba(255,255,255,0.06)" }}
    >
      <div
        className="h-1.5 rounded transition-all duration-500"
        style={{
          width: `${Math.round(v * 100)}%`,
          background: color,
        }}
      />
    </div>
  );
}

export default function CongestionIntelligenceCard({ status, summary, hotspots }) {
  // Disabled state.
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
              Congestion Intelligence
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
          Set <code>MARITIME_CONGESTION_ENABLED=1</code> to opt in. The
          congestion layer is OFF by default. Phase 6 stops at the
          intelligence foundation; it does NOT touch the optimizer.
        </div>
      </div>
    );
  }

  const state = status.state || "unknown";
  const color = STATE_COLOR[state] || "#64748b";
  const label = STATE_LABEL[state] || state.toUpperCase();
  const synthetic = !!status.synthetic;
  const s = summary && summary.records && summary.records[0]
    ? summary.records[0] : null;
  const averageScore = s ? Number(s.average_score) || 0 : 0;
  const averageConf = s ? Number(s.average_confidence) || 0 : 0;
  const maxScore = s ? Number(s.max_score) || 0 : 0;
  const byLevel = s && s.by_level ? s.by_level : { low: 0, moderate: 0, high: 0, severe: 0 };
  const level =
    maxScore >= 0.85 ? "severe"
    : maxScore >= 0.65 ? "high"
    : maxScore >= 0.40 ? "moderate"
    : "low";
  const levelColor = LEVEL_COLOR[level] || "#64748b";

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
            Congestion Intelligence
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
          {synthetic && (
            <div
              className="text-xs font-mono px-2 py-1 rounded"
              title="Records are produced from bundled synthetic fixtures."
              style={{
                background: "rgba(99,102,241,0.15)",
                color: "#a5b4fc",
                border: "1px solid rgba(99,102,241,0.3)",
              }}
            >
              SYNTHETIC
            </div>
          )}
          {!synthetic && (
            <div
              className="text-xs font-mono px-2 py-1 rounded"
              style={{
                background: "rgba(16,185,129,0.12)",
                color: "#10b981",
                border: "1px solid rgba(16,185,129,0.3)",
              }}
            >
              DERIVED
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-5 gap-3 mb-3">
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            Max Score
          </div>
          <div
            className="text-lg font-mono"
            style={{ color: levelColor }}
          >
            {maxScore ? maxScore.toFixed(2) : "—"}
          </div>
          <div
            className="text-[10px] font-mono"
            style={{ color: levelColor }}
          >
            {LEVEL_LABEL[level] || "—"}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            Avg Score
          </div>
          <div className="text-sm text-white/80 font-mono">
            {averageScore ? averageScore.toFixed(2) : "—"}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            Confidence
          </div>
          <div className="text-sm text-white/80 font-mono">
            {averageConf ? averageConf.toFixed(2) : "—"}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            Entities
          </div>
          <div className="text-sm text-white/80 font-mono">
            {formatNumber(status.record_count)}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            Freshness
          </div>
          <div className="text-sm text-white/80 font-mono">
            {formatAge(status.freshness_seconds)}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-3">
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            LOW
          </div>
          <div className="text-sm font-mono" style={{ color: LEVEL_COLOR.low }}>
            {byLevel.low ?? 0}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            MODERATE
          </div>
          <div className="text-sm font-mono" style={{ color: LEVEL_COLOR.moderate }}>
            {byLevel.moderate ?? 0}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            HIGH
          </div>
          <div className="text-sm font-mono" style={{ color: LEVEL_COLOR.high }}>
            {byLevel.high ?? 0}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">
            SEVERE
          </div>
          <div className="text-sm font-mono" style={{ color: LEVEL_COLOR.severe }}>
            {byLevel.severe ?? 0}
          </div>
        </div>
      </div>

      <div
        className="text-[11px] font-mono text-white/40 leading-relaxed pt-3"
        style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
      >
        <div className="flex items-center gap-2 mb-2">
          <span className="text-white/30">Inputs:</span>
          {(status.inputs_present || []).map((s) => (
            <span
              key={s}
              className="text-[9px] px-1 rounded"
              style={{
                background: "rgba(16,185,129,0.12)",
                color: "#10b981",
              }}
            >
              {s}
            </span>
          ))}
          {(status.inputs_missing || []).map((s) => (
            <span
              key={s}
              className="text-[9px] px-1 rounded"
              style={{
                background: "rgba(255,255,255,0.05)",
                color: "#94a3b8",
              }}
            >
              {s}·missing
            </span>
          ))}
        </div>
        <div className="text-white/30">
          Score weights: traffic · traffic_change · port_pressure ·
          weather_risk. Quality / freshness only ever reduce confidence,
          never inflate the score.
        </div>
      </div>
    </div>
  );
}
