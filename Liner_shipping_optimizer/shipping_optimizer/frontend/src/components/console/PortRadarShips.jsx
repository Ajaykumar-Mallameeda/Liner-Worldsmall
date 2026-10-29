/**
 * PortRadarShips.jsx
 * ------------------
 * Sentinel-1 radar ship count around one port (feature #10), on demand: backend/sarships.py counts bright targets
 * on water (ESA WorldCover mask, ratio CFAR) in the latest Sentinel-1 IW passes over a 16 x 16 km square centred
 * on the PortWatch port point (else the dataset point). Shows the count per pass, the radar crop of the chosen
 * pass with its targets boxed, and what the number does and does not include.
 */

import React, { useEffect, useState } from 'react';
import { usePortLocation } from '../../services/portLocate.js';
import { SourceChip } from '../common/Figure.jsx';

const HALF_KM = 8;
const SCENES = 4;
const results = new Map(); // `${code}|${lat}|${lon}` -> response, kept while the page lives

function when(iso) {
  const d = new Date(iso);
  return `${d.toISOString().slice(0, 10)} ${d.toISOString().slice(11, 16)} UTC`;
}

export default function PortRadarShips({ code }) {
  const { dataset, portwatch, loaded } = usePortLocation(code);
  const centre = portwatch ? [portwatch.lon, portwatch.lat] : dataset;
  const key = centre ? `${code}|${centre[1].toFixed(4)}|${centre[0].toFixed(4)}` : null;
  const [data, setData] = useState(() => (key ? results.get(key) || null : null));
  const [state, setState] = useState('idle'); // idle | loading | error
  const [error, setError] = useState(null);
  const [pick, setPick] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => { setData(key ? results.get(key) || null : null); setState('idle'); setError(null); setPick(0); }, [key]);

  useEffect(() => {
    if (state !== 'loading') return undefined;
    const t0 = Date.now();
    const id = setInterval(() => setElapsed(Math.round((Date.now() - t0) / 1000)), 1000);
    return () => clearInterval(id);
  }, [state]);

  const run = () => {
    if (!centre) return;
    setState('loading'); setElapsed(0); setError(null);
    const q = new URLSearchParams({ code, lat: centre[1].toFixed(5), lon: centre[0].toFixed(5), half_km: String(HALF_KM), scenes: String(SCENES) });
    fetch(`/api/sar/ships?${q}`)
      .then(async (r) => {
        const j = await r.json().catch(() => null);
        if (!r.ok) throw new Error(j?.detail || `HTTP ${r.status}`);
        return j;
      })
      .then((j) => { results.set(key, j); setData(j); setPick(0); setState('idle'); })
      .catch((e) => { setError(e.message || String(e)); setState('error'); });
  };

  if (!dataset) return null;
  const scenes = data?.scenes || [];
  const counted = scenes.filter((s) => s.ships != null);
  const max = Math.max(1, ...counted.map((s) => s.ships));
  const shown = scenes[pick] || null;
  const where = portwatch ? `PortWatch "${portwatch.name}"` : 'the dataset port point';

  return (
    <div className="ps-wrap">
      <div className="ps-head">
        <span>Sentinel-1 radar ship count</span>
        {data && <button type="button" className="rs-btn" onClick={run} disabled={state === 'loading'}>Recount</button>}
      </div>

      {!data && (
        <div className="rs-intro">
          <p>
            Counts bright targets on water in the last {SCENES} Sentinel-1 radar passes over a {HALF_KM * 2} × {HALF_KM * 2} km
            square around {loaded ? where : '…'}. Radar sees through cloud and at night. The first count takes 20–40 s.
          </p>
          <button type="button" className="rs-btn rs-primary" onClick={run} disabled={state === 'loading' || !loaded}>
            {state === 'loading' ? `Counting… ${elapsed}s` : 'Count ships'}
          </button>
        </div>
      )}
      {state === 'error' && (
        <div className="rs-error" role="alert">Radar counts are unavailable right now ({error}). The source is Microsoft Planetary Computer; try again in a minute.</div>
      )}

      {data && (
        <>
          <div className="rs-kpis">
            <div><span>Latest pass</span><b>{data.summary.latest ?? '—'}</b><SourceChip src="Sentinel-1 radar" def="bright targets on water, 500–60,000 m²" /></div>
            <div><span>Median · {data.summary.scenes_counted} passes</span><b>{data.summary.median ?? '—'}</b><SourceChip src="Sentinel-1 radar" def="median of the passes counted" /></div>
            <div><span>Water in square</span><b>{counted[0]?.water_km2 ?? '—'} km²</b><SourceChip src="ESA WorldCover 2021" def="open water in the square" /></div>
          </div>
          <ul className="rs-scenes" aria-label="Passes">
            {scenes.map((s, i) => (
              <li key={s.id}>
                <button type="button" aria-pressed={i === pick} onClick={() => setPick(i)} title={s.id}>
                  <span className="rs-when">{when(s.datetime)} · {s.orbit === 'ascending' ? 'asc' : 'desc'}</span>
                  <span className="rs-bar" aria-hidden="true"><span style={{ width: s.ships != null ? `${(s.ships / max) * 100}%` : 0 }} /></span>
                  <span className="rs-n">{s.ships != null ? s.ships : s.error ? 'error' : 'partial'}</span>
                </button>
              </li>
            ))}
          </ul>
          {shown?.image && (
            <figure className="rs-fig">
              <img src={shown.image} alt={`Sentinel-1 VV radar crop ${when(shown.datetime)}: ${shown.ships} targets boxed`} />
              <figcaption>
                <span><i className="rs-key rs-key-box" /> target</span>
                <span><i className="rs-key rs-key-water" /> water (WorldCover)</span>
                <span>{HALF_KM * 2} km square · north up · ~{shown.pixel_m?.[0]} m/px</span>
              </figcaption>
            </figure>
          )}
          {state === 'loading' && <div className="text-slate-400">Recounting… {elapsed}s</div>}
          <ul className="rs-notes">
            <li>Counts ships moored, at anchor and under way, plus buoys, platforms, wind turbines and bright quay structures over the water. Hulls moored side by side can merge into one; basins narrower than about 170 m are left out.</li>
            <li>An estimate to compare pass against pass at this port, not a census: no AIS ground truth (the radar archive runs 2–3 days behind live AIS).</li>
            <li>Land reclaimed after 2021 is still water in the WorldCover mask, so structures on it can be counted.</li>
          </ul>
        </>
      )}

      <div className="ps-foot">
        <span>
          Contains modified Copernicus Sentinel-1 data (ESA) via{' '}
          <a href="https://planetarycomputer.microsoft.com/dataset/sentinel-1-grd" target="_blank" rel="noreferrer">Microsoft Planetary Computer</a>
          {' '}· water mask{' '}
          <a href="https://esa-worldcover.org" target="_blank" rel="noreferrer">ESA WorldCover 2021</a> (CC BY 4.0)
          {data?.status?.listed_on ? ` · passes listed ${data.status.listed_on}` : ''}
        </span>
      </div>
    </div>
  );
}
