/**
 * ProvenanceStrip
 * ---------------
 * Phase 10 — uniform provenance / freshness / quality / source
 * footer for any intelligence view. Designed to make "where did
 * this data come from" a one-glance answer, not a buried
 * disclosure.
 *
 * The fields are all optional. Missing fields render as `—`
 * rather than fabricating a placeholder.
 *
 * Pure presentational.
 */
export default function ProvenanceStrip({
  source,
  sourceStatus,
  timestamp,
  ageSeconds,
  ageLabel,
  quality,
  confidence,
  license,
  attribution,
  recordCount,
  snapshotId,
  synthetic,
}) {
  function Item({ k, v }) {
    if (v == null || v === '') return null;
    return (
      <span className="inline-flex items-center">
        <span className="k">{k}</span>
        <span className="v">{v}</span>
      </span>
    );
  }
  function fmtAge(secs) {
    if (secs == null) return null;
    if (typeof ageLabel === 'string') return ageLabel;
    if (secs < 60) return `${Math.round(secs)}s`;
    if (secs < 3600) return `${Math.round(secs / 60)}m`;
    if (secs < 86400) return `${Math.round(secs / 3600)}h`;
    return `${Math.round(secs / 86400)}d`;
  }
  const qual = quality != null ? quality : confidence;
  const qualText = qual != null ? Number(qual).toFixed(2) : null;
  return (
    <div className="mc-provenance">
      <Item k="source" v={source} />
      <span className="sep" />
      <Item k="status" v={sourceStatus} />
      <span className="sep" />
      <Item k="timestamp" v={timestamp} />
      <span className="sep" />
      <Item k="age" v={fmtAge(ageSeconds)} />
      <span className="sep" />
      <Item k="quality" v={qualText} />
      {recordCount != null && (
        <>
          <span className="sep" />
          <Item k="records" v={recordCount} />
        </>
      )}
      {snapshotId != null && (
        <>
          <span className="sep" />
          <Item k="snapshot" v={String(snapshotId).slice(0, 20)} />
        </>
      )}
      {license != null && (
        <>
          <span className="sep" />
          <Item k="license" v={license} />
        </>
      )}
      {synthetic === true && (
        <>
          <span className="sep" />
          <span className="inline-flex items-center">
            <span className="k">provenance</span>
            <span className="v" style={{ color: '#c084fc' }}>
              synthetic
            </span>
          </span>
        </>
      )}
      {attribution != null && attribution !== '' && (
        <>
          <span className="sep" />
          <Item k="attribution" v={attribution} />
        </>
      )}
    </div>
  );
}
