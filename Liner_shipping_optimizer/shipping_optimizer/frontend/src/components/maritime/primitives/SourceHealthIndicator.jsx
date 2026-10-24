/**
 * SourceHealthIndicator
 * ---------------------
 * One-line row that surfaces a single maritime data source. The
 * canonical fields are:
 *
 *   source       — display name (e.g. "EMODNET")
 *   dataset      — short dataset slug (e.g. "emodnet_vessel_density")
 *   state        — "live" | "available" | "snapshot" | ...
 *   license      — short license label
 *   ageSeconds   — numeric age; rendered via DataFreshnessBadge
 *   quality      — numeric quality; rendered via ConfidenceIndicator
 *   record_count — number of records; rendered via TelemetryMetric
 *   snapshot_id  — short id (truncated)
 *   attribution  — optional long attribution (rendered in the footer)
 *
 * All fields are optional. The component degrades silently: any
 * missing field shows a quiet "—". The shape is intended to be a
 * superset of the per-source entries on the existing maritime
 * views so the Phase 8 refactor can unify them.
 *
 * Pure presentational. The parent passes the row data in.
 */

import { useState } from 'react';
import MaritimeStatusBadge from './MaritimeStatusBadge.jsx';
import DataFreshnessBadge, { formatAgeSeconds } from './DataFreshnessBadge.jsx';
import ConfidenceIndicator from './ConfidenceIndicator.jsx';

function compactNumber(n) {
  if (n == null) return '—';
  const num = Number(n);
  if (!Number.isFinite(num)) return '—';
  if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
  if (num >= 1e3) return `${(num / 1e3).toFixed(1)}k`;
  return String(Math.round(num));
}

function truncate(value, max = 18) {
  if (!value) return '—';
  const s = String(value);
  if (s.length <= max) return s;
  return `${s.slice(0, max - 3)}...`;
}

export default function SourceHealthIndicator({
  source,
  dataset,
  state = 'unknown',
  license,
  ageSeconds,
  freshnessSeconds, // alias accepted so callers from the
                    // /api/maritime/overview endpoint don't
                    // have to remap
  quality,
  qualityScore,     // alias
  recordCount,
  recordCountAlt,   // alias
  snapshotId,
  attribution,
  live = false,
  onClick,
}) {
  const [open, setOpen] = useState(false);
  const age = ageSeconds != null ? ageSeconds : freshnessSeconds;
  const q = quality != null ? quality : qualityScore;
  const rc = recordCount != null ? recordCount : recordCountAlt;
  const expandable = Boolean(attribution) || Boolean(snapshotId);
  return (
    <div
      className="rounded-lg px-3 py-2 transition-all duration-300"
      style={{
        background: 'rgba(2,12,24,0.55)',
        border: '1px solid rgba(148,163,184,0.16)',
        cursor: expandable || onClick ? 'pointer' : 'default',
      }}
      onClick={() => {
        if (onClick) onClick();
        else if (expandable) setOpen((v) => !v);
      }}
      role={expandable || onClick ? 'button' : undefined}
      tabIndex={expandable || onClick ? 0 : undefined}
      onKeyDown={(e) => {
        if (!expandable && !onClick) return;
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (onClick) onClick();
          else setOpen((v) => !v);
        }
      }}
    >
      <div className="flex items-center justify-between gap-3 min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <MaritimeStatusBadge value={state} pulse={live} />
          <span className="text-white/85 text-[12px] font-mono truncate">
            {source || '—'}
          </span>
          {dataset && (
            <span className="text-white/60 text-[12px] font-mono truncate">
              · {dataset}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4 flex-shrink-0">
          {license && (
            <span
              className="text-white/35 text-[12px] font-mono uppercase tracking-widest hidden md:inline"
              title={license}
            >
              {license.length > 24 ? `${license.slice(0, 21)}...` : license}
            </span>
          )}
          <DataFreshnessBadge ageSeconds={age} />
          {q != null && (
            <ConfidenceIndicator value={q} showBar={false} />
          )}
          {rc != null && (
            <span
              className="text-white/55 text-[12px] font-mono tabular-nums"
              title={`${rc} records`}
            >
              {compactNumber(rc)} rec
            </span>
          )}
        </div>
      </div>
      {open && expandable && (
        <div
          className="mt-2 pt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[12px] font-mono"
          style={{ borderTop: '1px solid rgba(148,163,184,0.10)' }}
        >
          <div className="text-white/60">snapshot_id</div>
          <div
            className="text-white/70 text-right truncate"
            title={snapshotId}
          >
            {snapshotId || '—'}
          </div>
          {attribution && (
            <>
              <div className="text-white/60 col-span-2 mt-1">attribution</div>
              <div className="text-white/55 col-span-2 text-[12px] leading-snug">
                {attribution}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
