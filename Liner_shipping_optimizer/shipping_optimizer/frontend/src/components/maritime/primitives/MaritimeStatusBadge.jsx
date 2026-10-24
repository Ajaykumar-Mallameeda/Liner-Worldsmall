/**
 * MaritimeStatusBadge
 * --------------------
 * Canonical status pill for the Phase 8 maritime command center.
 * Wraps the existing `PulseDot` primitive so the pulse animation
 * is not duplicated. The color/label table is a strict superset
 * of the per-source tables in:
 *   - MaritimeStatusCard.jsx (healthy/available/degraded/...)
 *   - LiveMaritimeIntelligenceCard.jsx (live/cached/...)
 *   - WeatherIntelligenceCard.jsx (available/checking/...)
 *   - CongestionIntelligenceCard.jsx (available/checking/...)
 * and adds LIVE / SNAPSHOT / HISTORICAL / UNKNOWN which are
 * referenced in the Phase 8 brief.
 *
 * Pure presentational. The parent view decides what state to pass
 * in; the badge never calls fetch.
 */

import PulseDot from '../../common/PulseDot.jsx';

export const MARITIME_STATE_COLOR = {
  live: '#10b981',
  available: '#10b981',
  snapshot: '#38bdf8',
  historical: '#94a3b8',
  checking: '#38bdf8',
  degraded: '#f59e0b',
  stale: '#f59e0b',
  invalid: '#ef4444',
  offline: '#ef4444',
  error: '#ef4444',
  disabled: '#64748b',
  unknown: '#64748b',
};

export const MARITIME_STATE_LABEL = {
  live: 'LIVE',
  available: 'AVAILABLE',
  snapshot: 'SNAPSHOT',
  historical: 'HISTORICAL',
  checking: 'CHECKING',
  degraded: 'DEGRADED',
  stale: 'STALE',
  invalid: 'INVALID',
  offline: 'OFFLINE',
  error: 'ERROR',
  disabled: 'DISABLED',
  unknown: 'UNKNOWN',
};

export const MARITIME_STATE_ORDER = [
  'live',
  'available',
  'snapshot',
  'historical',
  'checking',
  'degraded',
  'stale',
  'invalid',
  'offline',
  'error',
  'disabled',
  'unknown',
];

export default function MaritimeStatusBadge({
  value = 'unknown',
  pulse = true,
  withDot = true,
  size = 'sm',
  title,
}) {
  const key = String(value || 'unknown').toLowerCase();
  const color = MARITIME_STATE_COLOR[key] || MARITIME_STATE_COLOR.unknown;
  const label = MARITIME_STATE_LABEL[key] || 'UNKNOWN';
  const sizeStyle =
    size === 'lg'
      ? { fontSize: 12, padding: '2px 8px' }
      : size === 'md'
        ? { fontSize: 12, padding: '2px 7px' }
        : { fontSize: 12, padding: '1px 6px' };
  return (
    <span
      className="maritime-state-change inline-flex items-center gap-1.5"
      style={{ color }}
      title={title || label}
    >
      {withDot && (pulse ? <PulseDot color={color} /> : (
        <span
          className="inline-block rounded-full"
          style={{ width: 8, height: 8, backgroundColor: color }}
        />
      ))}
      <span
        className="font-mono uppercase tracking-widest"
        style={sizeStyle}
      >
        {label}
      </span>
    </span>
  );
}
