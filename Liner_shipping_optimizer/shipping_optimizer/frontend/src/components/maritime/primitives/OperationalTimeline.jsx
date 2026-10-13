/**
 * OperationalTimeline
 * -------------------
 * Phase 9 — Feature B. A reusable event timeline primitive for
 * the maritime command center. Renders a list of operator-readable
 * events in descending time order. Each event supports:
 *
 *   - timestamp (ISO 8601 string; may be null)
 *   - source     (string; dataset or provider name)
 *   - state      (one of the documented maritime state tokens)
 *   - severity   (info | ok | warn | critical)
 *   - title      (one-line summary)
 *   - description (operator-readable line)
 *   - feature    (optional; the IP-5 feature name)
 *   - confidence (optional; numeric)
 *   - details    (optional; small key-value block, rendered
 *                 when the row is expanded)
 *
 * The component is purely presentational. It does NOT derive
 * events. The parent view is responsible for assembling the
 * events array from real runtime/artifact/backend state. The
 * companion helper `deriveMaritimeEvents` lives in the same
 * file (kept pure) so the tests can drive it directly.
 *
 * Accessibility:
 *   - rows are <button>s (Enter/Space) when expandable
 *   - state is communicated via both the colour pill AND the
 *     written label (never colour-alone)
 */

import { useState } from 'react';
import MaritimeStatusBadge, {
  MARITIME_STATE_LABEL,
} from './MaritimeStatusBadge.jsx';

const SEVERITY_COLOR = {
  info: '#38bdf8',
  ok: '#10b981',
  warn: '#f59e0b',
  critical: '#ef4444',
};

const SEVERITY_LABEL = {
  info: 'INFO',
  ok: 'OK',
  warn: 'WARN',
  critical: 'CRITICAL',
};

function fmtTimestamp(iso) {
  if (!iso) return '—';
  try {
    return iso.replace('T', ' ').replace('Z', ' UTC').slice(0, 19);
  } catch (_) {
    return iso;
  }
}

function pickSeverity(event) {
  if (event && event.severity && SEVERITY_COLOR[event.severity]) {
    return event.severity;
  }
  const s = String((event && event.state) || 'unknown').toLowerCase();
  if (s === 'live' || s === 'available' || s === 'snapshot') return 'ok';
  if (s === 'degraded' || s === 'stale') return 'warn';
  if (s === 'offline' || s === 'error' || s === 'invalid') return 'critical';
  return 'info';
}

function pickStateBadge(event) {
  const s = String((event && event.state) || 'unknown').toLowerCase();
  if (MARITIME_STATE_LABEL[s]) return s;
  return 'unknown';
}

export default function OperationalTimeline({
  events = [],
  emptyMessage = 'No events to display.',
  maxInitial = 25,
}) {
  const [openIdx, setOpenIdx] = useState(-1);

  if (!Array.isArray(events) || events.length === 0) {
    return (
      <div className="text-[11px] text-white/35 font-mono">
        {emptyMessage}
      </div>
    );
  }

  // Sort by timestamp descending when timestamps are parseable.
  // Events with no timestamp are placed at the bottom.
  const sorted = [...events].sort((a, b) => {
    const ta = a && a.timestamp ? Date.parse(a.timestamp) : NaN;
    const tb = b && b.timestamp ? Date.parse(b.timestamp) : NaN;
    if (Number.isFinite(ta) && Number.isFinite(tb)) return tb - ta;
    if (Number.isFinite(ta)) return -1;
    if (Number.isFinite(tb)) return 1;
    return 0;
  });

  const visible = sorted.slice(0, maxInitial);

  return (
    <ol
      className="flex flex-col gap-1.5"
      aria-label="Operational event timeline"
    >
      {visible.map((event, idx) => {
        const sev = pickSeverity(event);
        const badgeState = pickStateBadge(event);
        const hasDetails = event && event.details
          && typeof event.details === 'object'
          && Object.keys(event.details).length > 0;
        const open = openIdx === idx;
        const lineColor = SEVERITY_COLOR[sev] || SEVERITY_COLOR.info;
        return (
          <li
            key={`${event.timestamp || 'untimed'}-${idx}`}
            className="rounded-lg"
            style={{
              background: 'rgba(2,12,24,0.5)',
              border: `1px solid ${lineColor}22`,
              borderLeft: `3px solid ${lineColor}`,
            }}
          >
            <button
              type="button"
              className="w-full text-left px-3 py-2 flex items-center gap-3 min-w-0"
              onClick={() => hasDetails && setOpenIdx(open ? -1 : idx)}
              aria-expanded={hasDetails ? open : undefined}
              disabled={!hasDetails}
              style={{ cursor: hasDetails ? 'pointer' : 'default' }}
            >
              <span
                className="font-mono uppercase tracking-widest text-[9px]"
                style={{ color: lineColor, minWidth: 50 }}
              >
                {SEVERITY_LABEL[sev]}
              </span>
              <MaritimeStatusBadge value={badgeState} pulse={false} size="sm" />
              <div className="flex-1 min-w-0">
                <div className="text-[12px] font-mono text-white/85 truncate">
                  {event.title || event.description || 'event'}
                </div>
                {event.description && event.title && (
                  <div className="text-[10px] font-mono text-white/45 truncate">
                    {event.description}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {event.source && (
                  <span className="text-[9px] font-mono text-white/35 uppercase tracking-widest">
                    {event.source}
                  </span>
                )}
                <span className="text-[10px] font-mono text-white/40 tabular-nums">
                  {fmtTimestamp(event.timestamp)}
                </span>
              </div>
            </button>
            {open && hasDetails && (
              <div
                className="px-3 pb-2 pt-1 grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] font-mono"
                style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
              >
                {Object.entries(event.details).map(([k, v]) => (
                  <div key={k} className="contents">
                    <div className="text-white/40">{k}</div>
                    <div
                      className="text-white/70 text-right truncate"
                      title={typeof v === 'string' ? v : undefined}
                    >
                      {v == null ? '—' : String(v)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </li>
        );
      })}
      {sorted.length > maxInitial && (
        <li className="text-[10px] font-mono text-white/30 mt-1">
          showing {maxInitial} of {sorted.length} events (newest first)
        </li>
      )}
    </ol>
  );
}

/* -----------------------------------------------------------------
 * Pure helper: deriveMaritimeEvents
 * ---------------------------------
 * Phase 9 — Feature B. Build an event list from real runtime
 * and artifact state. NEVER fabricates a timestamp or state. If
 * a piece of data is missing, the corresponding event is omitted
 * (or rendered with state="unknown" + an explicit "data
 * unavailable" description).
 *
 * The helper is exported so tests can drive it directly.
 * ----------------------------------------------------------------- */

export function deriveMaritimeEvents({
  overview = null,
  routingImpact = null,
  pipelineOutput = null,
} = {}) {
  const events = [];

  // 1) Maritime-intelligence initialization (artifact level).
  if (pipelineOutput && pipelineOutput.maritime_intelligence) {
    const mi = pipelineOutput.maritime_intelligence;
    events.push({
      timestamp: mi.retrieved_at || null,
      source: 'maritime',
      state: mi.budget_exceeded ? 'degraded' : 'available',
      severity: mi.budget_exceeded ? 'warn' : 'ok',
      title: 'Maritime intelligence initialised',
      description: mi.budget_exceeded
        ? 'attach exceeded its wall-clock budget; some features dropped'
        : 'attach completed within budget',
      confidence: null,
      feature: null,
      details: {
        snapshot_id: mi.snapshot_id,
        duration_ms: mi.duration_ms,
        budget_exceeded: mi.budget_exceeded ? 'true' : 'false',
      },
    });
  }

  // 2) Per-source health events.
  if (overview && overview.sources && typeof overview.sources === 'object') {
    for (const [key, cell] of Object.entries(overview.sources)) {
      if (!cell || typeof cell !== 'object') continue;
      const s = String(cell.state || 'unknown').toLowerCase();
      events.push({
        timestamp: null, // source object has no per-row timestamp
        source: key,
        state: MARITIME_STATE_LABEL[s] ? s : 'unknown',
        severity:
          s === 'live' || s === 'available' || s === 'snapshot' ? 'ok'
            : s === 'degraded' || s === 'stale' ? 'warn'
              : s === 'offline' || s === 'error' ? 'critical'
                : 'info',
        title: `source ${key} reported ${s}`,
        description: cell.error
          ? `sub-endpoint error: ${cell.error}`
          : `provider=${cell.provider || '—'} snapshot=${cell.snapshot_id || '—'}`,
        confidence: cell.quality_score,
        feature: null,
        details: {
          provider: cell.provider,
          snapshot_id: cell.snapshot_id,
          freshness_seconds: cell.freshness_seconds,
          quality: cell.quality_score,
        },
      });
    }
  }

  // 3) Per-feature events (from routing-impact payload, IP-5).
  if (routingImpact && Array.isArray(routingImpact.features)) {
    for (const f of routingImpact.features) {
      if (!f || !f.feature) continue;
      const s = String(f.state || 'unknown').toLowerCase();
      const titleByState = {
        applied: `Feature ${f.feature} applied to optimizer`,
        rejected: `Feature ${f.feature} rejected (confidence floor)`,
        stale: `Feature ${f.feature} stale (past max-age)`,
        fallback_used: `Feature ${f.feature} fallback used`,
        baseline: `Feature ${f.feature} baseline retained`,
      };
      events.push({
        timestamp: routingImpact.retrieved_at || null,
        source: f.feature,
        state: s,
        severity:
          s === 'applied' ? 'ok'
            : s === 'rejected' || s === 'stale' ? 'warn'
              : s === 'fallback_used' ? 'warn'
                : 'info',
        title: titleByState[s] || `Feature ${f.feature} status ${s}`,
        description: f.reason || null,
        confidence: f.confidence,
        feature: f.feature,
        details: {
          speed_factor: f.speed_factor,
          score: f.score,
          level: f.level,
          freshness_state: f.freshness_state,
          synthetic: f.synthetic ? 'true' : 'false',
        },
      });
    }
  }

  return events;
}
