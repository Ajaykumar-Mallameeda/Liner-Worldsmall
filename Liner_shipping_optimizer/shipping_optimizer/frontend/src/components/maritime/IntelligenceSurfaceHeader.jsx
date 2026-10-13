/**
 * IntelligenceSurfaceHeader
 * --------------------------
 * Phase 10 — the uniform header at the top of every maritime
 * intelligence view. Carries:
 *
 *   - eyebrow    (small mono caps, accent color)
 *   - title      (display)
 *   - subtitle   (one-line prose)
 *   - status pill (LIVE / AVAILABLE / STALE / OFFLINE / …)
 *   - right slot (e.g. last-evaluated timestamp, source filter rail)
 *
 * The visual contract is additive over Phase 8: the dark glass,
 * the cyan accent rule, and the system font are unchanged. The
 * only new asset is the uniform surface treatment so a user
 * recognises the surface from the first 200 ms of focus.
 *
 * Pure presentational. Never reaches outside its own subtree.
 */
import { useMemo } from 'react';
import MaritimeStatusBadge from './primitives/MaritimeStatusBadge.jsx';

function fmtTimestamp(iso) {
  if (!iso) return '—';
  try {
    return iso.replace('T', ' ').replace('Z', ' UTC').slice(0, 19);
  } catch (_) {
    return iso;
  }
}

export default function IntelligenceSurfaceHeader({
  eyebrow,
  title,
  subtitle,
  overallState = 'unknown',
  evaluatedAt,
  right,
}) {
  const evaluatedLabel = useMemo(() => fmtTimestamp(evaluatedAt), [evaluatedAt]);
  return (
    <div className="mc-surface-header">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          {eyebrow && <div className="mc-surface-eyebrow">{eyebrow}</div>}
          <div className="mc-surface-title">{title}</div>
          {subtitle && <div className="mc-surface-subtitle">{subtitle}</div>}
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {right}
          <div className="flex items-center gap-2">
            <span
              className="mono-data"
              style={{
                fontSize: 9,
                color: 'var(--maritime-ink-faint)',
                textTransform: 'uppercase',
                letterSpacing: '0.18em',
              }}
            >
              overall
            </span>
            <MaritimeStatusBadge
              value={overallState}
              pulse={overallState === 'live'}
              size="md"
            />
          </div>
        </div>
      </div>
      {evaluatedAt != null && (
        <div
          className="mt-3 flex items-center gap-3 mono-data"
          style={{
            fontSize: 10,
            color: 'var(--maritime-ink-soft)',
          }}
        >
          <span
            style={{
              color: 'var(--maritime-ink-faint)',
              textTransform: 'uppercase',
              letterSpacing: '0.18em',
            }}
          >
            last evaluated
          </span>
          <span>{evaluatedLabel}</span>
        </div>
      )}
    </div>
  );
}
