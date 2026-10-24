/**
 * Figure parts shared by headline tiles:
 *   UnitValue   "$45.0M" → number in full ink, currency and unit set smaller and dimmer
 *   Sparkline   one value per iteration; the iteration on screen is marked
 *   Provenance  "where does this number come from": file, field, run — a click-open popover
 */

import React, { useEffect, useId, useRef, useState } from 'react';

const SPLIT = /^([−-]?)(\$?)([\d.,]+)\s*([A-Za-z%]*)(.*)$/;

export function UnitValue({ text }) {
  const m = SPLIT.exec(String(text ?? ''));
  if (!m) return <>{text}</>;
  const [, sign, cur, num, unit, rest] = m;
  return (
    <>
      {sign}
      {cur && <span className="u u-pre">{cur}</span>}
      {num}
      {unit && <span className="u">{unit === '%' ? '%' : unit}</span>}
      {rest}
    </>
  );
}

export function Sparkline({ values = [], active = -1, label, width = 72, height = 20 }) {
  const pts = values.map((v, i) => [i, v]).filter(([, v]) => v != null && Number.isFinite(Number(v)));
  if (pts.length < 2) return null;
  const ys = pts.map(([, v]) => Number(v));
  const lo = Math.min(...ys); const hi = Math.max(...ys);
  const x = (i) => 3 + (i / (values.length - 1)) * (width - 6);
  const y = (v) => (hi === lo ? height / 2 : 3 + (1 - (v - lo) / (hi - lo)) * (height - 6));
  return (
    <svg className="spk" width={width} height={height} role="img" aria-label={label}>
      <polyline points={pts.map(([i, v]) => `${x(i)},${y(Number(v))}`).join(' ')} />
      <title>{label}</title>
      {pts.map(([i, v]) => <circle key={i} cx={x(i)} cy={y(Number(v))} r={i === active ? 3 : 1.5} className={i === active ? 'is-on' : ''} />)}
    </svg>
  );
}

/** rows: [[label, value], ...] */
export function Provenance({ rows = [], label = 'Where this number comes from' }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const box = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);
  return (
    <span className="prov" ref={box}>
      <button type="button" className="prov-btn" aria-expanded={open} aria-controls={id} aria-label={label} title={label} onClick={() => setOpen((v) => !v)}>i</button>
      {open && (
        <span className="prov-pop" id={id} role="dialog" aria-label={label}>
          {rows.filter(([, v]) => v != null && v !== '').map(([k, v]) => (
            <span className="prov-row" key={k}><span className="prov-k">{k}</span><span className="prov-v">{v}</span></span>
          ))}
        </span>
      )}
    </span>
  );
}
