/**
 * DataFreshnessBadge
 * ------------------
 * Derives a FRESH / AGING / STALE / OFFLINE / UNKNOWN badge from
 * a numeric age (in seconds). The thresholds are intentionally
 * conservative and mirror the Phase 3 source-health classifier:
 *
 *   age < 0              -> invalid (offline-class)
 *   age <= 900s   (15m)  -> FRESH
 *   age <= 86400s (24h)  -> AGING
 *   age > 86400s         -> STALE
 *   age == null/unknown  -> UNKNOWN
 *
 * The thresholds are local to the dashboard — they do not
 * override any backend classifier; the backend is authoritative
 * and the dashboard simply mirrors the result.
 */

import { MARITIME_STATE_COLOR, MARITIME_STATE_LABEL } from './MaritimeStatusBadge.jsx';

const FRESH_THRESHOLD_S = 15 * 60;       // 15 min
const STALE_THRESHOLD_S = 24 * 60 * 60;  // 24 h

function derive(ageSeconds) {
  if (ageSeconds == null || ageSeconds === '') {
    return { state: 'unknown', label: 'UNKNOWN' };
  }
  const n = Number(ageSeconds);
  if (!Number.isFinite(n) || n < 0) {
    return { state: 'offline', label: 'INVALID' };
  }
  if (n <= FRESH_THRESHOLD_S) {
    return { state: 'available', label: 'FRESH' };
  }
  if (n <= STALE_THRESHOLD_S) {
    return { state: 'historical', label: 'AGING' };
  }
  return { state: 'stale', label: 'STALE' };
}

function formatAge(ageSeconds) {
  if (ageSeconds == null) return '—';
  const n = Number(ageSeconds);
  if (!Number.isFinite(n) || n < 0) return '—';
  if (n < 1) return '<1s';
  if (n < 60) return `${Math.round(n)}s`;
  const m = Math.floor(n / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  return `${d}d`;
}

export default function DataFreshnessBadge({ ageSeconds, hint, size = 'sm' }) {
  const { state, label } = derive(ageSeconds);
  const color = MARITIME_STATE_COLOR[state] || MARITIME_STATE_COLOR.unknown;
  const ageLabel = formatAge(ageSeconds);
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
      title={hint || `age ${ageLabel}`}
    >
      <span
        className="font-mono uppercase tracking-widest"
        style={sizeStyle}
      >
        {label}
      </span>
      <span
        className="font-mono"
        style={{
          color: 'rgba(255,255,255,0.45)',
          fontSize: 12,
          letterSpacing: '0.06em',
        }}
      >
        {ageLabel === '—' ? ageLabel : `${ageLabel} ago`}
      </span>
    </span>
  );
}

export { derive as deriveFreshness, formatAge as formatAgeSeconds };
