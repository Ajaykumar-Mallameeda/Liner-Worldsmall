/**
 * PageHead
 * --------
 * Persistent page header band. Crumbs (eyebrow + section),
 * title + subtitle, and right-side meta line.
 *
 * Used by every page in the console. Single source of identity.
 */

import { Pill } from './p12.jsx';

function fmtTime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  } catch (_) { return String(iso); }
}

export default function PageHead({
  eyebrow,
  section,
  title,
  subtitle,
  meta = [],
  pills = [],
  evaluatedAt,
  snapshotId,
}) {
  return (
    <header className="cx-page-head" role="region" aria-label={title}>
      <div>
        <div className="crumbs">
          {section && <span className="a">{section}</span>}
          {section && eyebrow && <span className="a">›</span>}
          {eyebrow && <span className="b">{eyebrow}</span>}
        </div>
        <div className="title">
          <span className="a">{title}</span>
          {subtitle && <span className="b">{subtitle}</span>}
        </div>
      </div>
      <div className="meta">
        {pills.length > 0 && (
          <span className="row" style={{ gap: 6 }}>
            {pills.map((p, i) => (
              <Pill key={i} tone={p.tone}>{p.label}</Pill>
            ))}
          </span>
        )}
        {evaluatedAt && (
          <span className="row">
            <span className="k">last eval</span>
            <span className="v">{fmtTime(evaluatedAt)}</span>
          </span>
        )}
        {snapshotId && (
          <span className="row">
            <span className="k">snapshot</span>
            <span className="v">{snapshotId}</span>
          </span>
        )}
        {meta.map((m, i) => (
          <span className="row" key={i}>
            <span className="k">{m.k}</span>
            <span className="v">{m.v ?? '—'}</span>
          </span>
        ))}
      </div>
    </header>
  );
}
