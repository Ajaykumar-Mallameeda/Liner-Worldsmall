/**
 * LayerPanel — the map's layer switcher: layers grouped by what they show (Plan · Demand · Environment, and
 * the Risk / Satellite groups as their layers arrive), each with its key and a "data as of" badge saying
 * where the numbers or pixels come from. Folded to one button until opened; on phones it opens as a sheet.
 *
 * Props
 *   groups   [{ id, label, items: [{ id, label, hint, on, onToggle, swatch, asOf, disabled, note }] }]
 *   basemap  { value, options: [{ key, label, asOf }], onChange }
 *   status   short line under the title (route geometry source)
 */
import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';

const PHONE = '(max-width: 767px)';
const isPhone = () => typeof window !== 'undefined' && window.matchMedia?.(PHONE).matches;

export default function LayerPanel({ groups = [], basemap = null, status = null }) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef(null);
  const [sheet, setSheet] = useState(isPhone);
  useEffect(() => {
    const mq = window.matchMedia?.(PHONE);
    if (!mq) return undefined;
    const on = () => setSheet(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);

  // Escape closes and hands focus back to the button.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') { setOpen(false); btnRef.current?.focus(); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const close = () => { setOpen(false); btnRef.current?.focus(); };
  const body = open ? (
    <div id="lp-panel" className={`lp-panel ${sheet ? 'lp-sheet' : ''}`} role={sheet ? 'dialog' : 'region'} aria-label="Map layers">
      <div className="lp-head">
        <span>Map layers</span>
        <button type="button" className="lp-close" onClick={close} aria-label="Close the layer panel">✕</button>
      </div>
      {status && <div className="lp-status">{status}</div>}
      {groups.filter((g) => g.items.length).map((g) => (
        <fieldset key={g.id} className="lp-group">
          <legend>{g.label}</legend>
          {g.items.map((it) => (
            <label key={it.id} className={`lp-item ${it.disabled ? 'is-disabled' : ''}`} title={it.hint || ''}>
              <input type="checkbox" checked={Boolean(it.on)} disabled={it.disabled} onChange={it.onToggle} />
              {it.swatch && <span className="lp-swatch" aria-hidden="true">{it.swatch}</span>}
              <span className="lp-label">
                {it.label}
                {it.note && <span className="lp-note">{it.note}</span>}
              </span>
              {it.asOf && <span className="lp-asof" title={`Data as of: ${it.asOf}`}>{it.asOf}</span>}
            </label>
          ))}
        </fieldset>
      ))}
      {basemap && (
        <fieldset className="lp-group">
          <legend>Environment · basemap</legend>
          {basemap.options.map((o) => (
            <label key={o.key} className="lp-item">
              <input type="radio" name={`lp-basemap-${basemap.name || 'map'}`} checked={basemap.value === o.key} onChange={() => basemap.onChange(o.key)} />
              <span className="lp-label">{o.label}</span>
              <span className="lp-asof" title={`Data as of: ${o.asOf}`}>{o.asOf}</span>
            </label>
          ))}
        </fieldset>
      )}
    </div>
  ) : null;
  // On phones the panel is a bottom sheet over the app chrome, so it goes to <body> with a backdrop.
  const panel = body && sheet
    ? createPortal(<><div className="lp-backdrop" onClick={close} aria-hidden="true" />{body}</>, document.body)
    : body;

  return (
    <div className="lp-root">
      <button ref={btnRef} type="button" className={`lp-btn ${open ? 'is-on' : ''}`} onClick={() => setOpen((v) => !v)}
        aria-expanded={open} aria-controls="lp-panel" title="Map layers and basemap">
        <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1 1 4.5 8 8l7-3.5L8 1Zm-5.6 6.2L1 8l7 3.5L15 8l-1.4-.8L8 10 2.4 7.2Zm0 3.5L1 11.5 8 15l7-3.5-1.4-.8L8 13.5l-5.6-2.8Z" fill="currentColor" /></svg>
        <span>Layers</span>
      </button>
      {panel}
    </div>
  );
}
