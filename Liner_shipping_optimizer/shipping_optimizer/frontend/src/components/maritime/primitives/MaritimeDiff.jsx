/**
 * MaritimeDiff
 * ------------
 * Phase 9 — Feature D. A presentational primitive that renders
 * the differences between two maritime telemetry snapshots.
 *
 * Each diff row shows:
 *   - metric name
 *   - previous value  (or em-dash)
 *   - delta symbol    (up / down / unchanged / unavailable)
 *   - current value   (or em-dash)
 *   - provenance (timestamp of the previous snapshot)
 *
 * Pure presentational. The companion helper
 * `deriveMaritimeDiff(previous, current)` builds the diff
 * structure from two snapshot objects; tests drive it
 * directly.
 *
 * The component never fabricates a previous snapshot. When
 * `previous === null` (or absent), the diff is reported as
 * "Previous snapshot unavailable" exactly as the brief
 * requires.
 */

const DELTA_GLYPH = {
  up: '↑',
  down: '↓',
  unchanged: '→',
  unavailable: '—',
};

const DELTA_COLOR = {
  up: '#10b981',
  down: '#f59e0b',
  unchanged: '#94a3b8',
  unavailable: '#64748b',
};

const DELTA_LABEL = {
  up: 'increased',
  down: 'decreased',
  unchanged: 'unchanged',
  unavailable: 'unavailable',
};

function fmtValue(v) {
  if (v == null) return '—';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return String(v);
    return v.toFixed(2);
  }
  return String(v);
}

export default function MaritimeDiff({
  diff = null,
  previousEvaluatedAt = null,
}) {
  if (!diff || !Array.isArray(diff.rows) || diff.rows.length === 0) {
    return (
      <div className="text-[12px] text-white/35 font-mono">
        Previous snapshot unavailable.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {previousEvaluatedAt && (
        <div className="text-[12px] font-mono text-white/35">
          previous snapshot: {previousEvaluatedAt.replace('T', ' ').replace('Z', ' UTC').slice(0, 19)}
        </div>
      )}
      <div
        className="grid grid-cols-1 md:grid-cols-2 gap-2"
        role="list"
        aria-label="Maritime telemetry diff"
      >
        {diff.rows.map((row) => {
          const color = DELTA_COLOR[row.delta] || DELTA_COLOR.unavailable;
          const glyph = DELTA_GLYPH[row.delta] || DELTA_GLYPH.unavailable;
          const label = DELTA_LABEL[row.delta] || 'unavailable';
          return (
            <div
              key={row.metric}
              role="listitem"
              className="rounded-lg px-3 py-2 flex items-center gap-3"
              style={{
                background: 'rgba(2,12,24,0.5)',
                border: '1px solid rgba(148,163,184,0.16)',
              }}
              title={`${row.metric}: ${label}`}
            >
              <span
                className="font-mono text-[12px] uppercase tracking-widest min-w-[110px]"
                style={{ color: 'rgba(255,255,255,0.45)' }}
              >
                {row.metric}
              </span>
              <div className="flex-1 flex items-center gap-2 min-w-0">
                <span className="font-mono tabular-nums text-[12px] text-white/55 truncate">
                  {fmtValue(row.previous)}
                </span>
                <span
                  className="font-mono text-[14px]"
                  style={{ color }}
                  aria-label={label}
                >
                  {glyph}
                </span>
                <span className="font-mono tabular-nums text-[12px] text-white/85 truncate">
                  {fmtValue(row.current)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* -----------------------------------------------------------------
 * Pure helper: deriveMaritimeDiff
 * --------------------------------
 * Phase 9 — Feature D. Build a diff from two telemetry
 * snapshots. NEVER fabricates a previous value. When the
 * previous snapshot is missing or invalid, every row is
 * reported as delta=unavailable with previous=null.
 * ----------------------------------------------------------------- */

function classifyDelta(prev, cur) {
  if (prev == null || cur == null) return 'unavailable';
  if (typeof prev !== 'number' || typeof cur !== 'number') {
    return prev === cur ? 'unchanged' : 'unavailable';
  }
  if (cur > prev) return 'up';
  if (cur < prev) return 'down';
  return 'unchanged';
}

export function deriveMaritimeDiff(previous, current) {
  if (!previous || !current) {
    return null;
  }
  if (!previous.fleet || !current.fleet) {
    return null;
  }
  const metrics = [
    'vessels_observed',
    'ports_observed',
    'weather_risk',
  ];
  const rows = [];
  for (const m of metrics) {
    rows.push({
      metric: m,
      previous: previous.fleet[m] ?? null,
      current: current.fleet[m] ?? null,
      delta: classifyDelta(previous.fleet[m] ?? null, current.fleet[m] ?? null),
    });
  }
  if (previous.processing && current.processing) {
    const pmetrics = ['duration_ms', 'sources_used_count', 'sources_missing_count'];
    for (const m of pmetrics) {
      rows.push({
        metric: m,
        previous: previous.processing[m] ?? null,
        current: current.processing[m] ?? null,
        delta: classifyDelta(previous.processing[m] ?? null, current.processing[m] ?? null),
      });
    }
  }
  return { rows };
}
