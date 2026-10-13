/**
 * ProviderStatusRow
 * -----------------
 * A compact, single-line row for listing a maritime provider
 * (e.g. "openmeteo", "digitraffic"). It supports the existing
 * non-commercial / commercial-safe pill convention from
 * MaritimeWeatherView so a row can communicate licensing at a
 * glance.
 *
 * Pure presentational.
 */

import MaritimeStatusBadge from './MaritimeStatusBadge.jsx';

export default function ProviderStatusRow({
  name,
  label,
  status = 'unknown',
  license,
  coverage,
  commercialSafe,
  attribution,
  url,
}) {
  return (
    <div
      className="rounded-lg p-2.5"
      style={{
        background: 'rgba(2,12,24,0.55)',
        border: '1px solid rgba(148,163,184,0.12)',
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-white/85 text-[12px] font-mono truncate">
            {label || name || '—'}
          </div>
          {coverage && (
            <div className="text-white/40 text-[10px] font-mono mt-0.5 truncate">
              {coverage}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {commercialSafe === false && (
            <span
              className="text-[9px] font-mono px-1.5 py-0.5 rounded"
              style={{
                background: 'rgba(245,158,11,0.15)',
                color: '#f59e0b',
                border: '1px solid rgba(245,158,11,0.3)',
              }}
              title="This provider's license is not cleared for commercial use."
            >
              NON-COMMERCIAL
            </span>
          )}
          {commercialSafe === true && (
            <span
              className="text-[9px] font-mono px-1.5 py-0.5 rounded"
              style={{
                background: 'rgba(16,185,129,0.12)',
                color: '#10b981',
                border: '1px solid rgba(16,185,129,0.3)',
              }}
              title="This provider's license permits commercial use."
            >
              COMMERCIAL-SAFE
            </span>
          )}
          <MaritimeStatusBadge value={status} pulse={false} />
        </div>
      </div>
      {(license || attribution) && (
        <div
          className="mt-1.5 pt-1.5 text-[10px] font-mono text-white/35 leading-relaxed"
          style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}
        >
          {license && (
            <div>
              <span className="text-white/25">license · </span>
              {license}
            </div>
          )}
          {attribution && (
            <div className="mt-0.5">
              <span className="text-white/25">attribution · </span>
              {attribution}
            </div>
          )}
          {url && (
            <div className="mt-0.5 truncate">
              <span className="text-white/25">endpoint · </span>
              <span title={url}>{url}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
