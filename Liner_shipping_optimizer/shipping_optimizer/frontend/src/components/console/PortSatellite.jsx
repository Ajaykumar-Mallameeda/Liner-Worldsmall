/**
 * PortSatellite.jsx
 * -----------------
 * Sentinel-2 view of one port (feature #9): a mosaic of EOX "Sentinel-2 cloudless" tiles centred on the
 * port's coordinates from the dataset, with a crosshair on that point, zoom, a year switch and a scale bar.
 *
 * Source: EOX IT Services WMTS (keyless), annual cloud-free mosaics of Copernicus Sentinel-2, 10 m native
 * resolution (about zoom 14). 2018 onwards are CC BY-NC-SA 4.0; the attribution line is required.
 * The tiles show the place, not the plan. Centre: IMF PortWatch's point for the port when the backend matches one
 * (/api/ports/locate: UN/LOCODE, else nearest within 30 km), else the dataset's point, which is often the city
 * (Rotterdam's sits 20 km from the port). The viewer can switch between the two; the crosshair marks the centre.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { getPortName } from '../../utils/portLookup.js';
import { usePortLocation } from '../../services/portLocate.js';
import { S2_YEARS, TILE, MIN_Z, MAX_Z, NATIVE_Z, s2TileUrl, scaleBar, tilesFor } from '../../utils/s2tiles.js';

export default function PortSatellite({ code, height = 200 }) {
  const { dataset: datasetCoords, portwatch: pw, loaded } = usePortLocation(code);
  const [centre, setCentre] = useState('portwatch');
  const boxRef = useRef(null);
  const [width, setWidth] = useState(320);
  const [z, setZ] = useState(13);
  const [year, setYear] = useState(S2_YEARS[0]);
  const [failed, setFailed] = useState(0);

  const usePw = Boolean(pw) && centre === 'portwatch';
  const coords = usePw ? [pw.lon, pw.lat] : datasetCoords;

  useEffect(() => {
    const el = boxRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(120, Math.round(entry.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, [coords == null]);

  useEffect(() => { setFailed(0); }, [code, z, year]);

  const tiles = useMemo(() => (coords ? tilesFor(coords[0], coords[1], z, width, height) : []), [coords?.[0], coords?.[1], z, width, height]);

  if (!coords) {
    return (
      <div className="ps-wrap">
        <div className="ps-head"><span>Sentinel-2 view</span></div>
        <div className="text-slate-400">No coordinates for {code} in the dataset, so there is no image.</div>
      </div>
    );
  }
  const [lon, lat] = coords;
  const bar = scaleBar(lat, z);
  const allFailed = tiles.length > 0 && failed >= tiles.length;

  return (
    <div className="ps-wrap">
      <div className="ps-head">
        <span>Sentinel-2 view</span>
        <span className="ps-controls">
          <select aria-label="Mosaic year" value={year} onChange={(e) => setYear(Number(e.target.value))} className="ps-select">
            {S2_YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <button type="button" className="ps-btn" onClick={() => setZ((v) => Math.max(MIN_Z, v - 1))} disabled={z <= MIN_Z} aria-label="Zoom satellite image out" title="Zoom image out">−</button>
          <button type="button" className="ps-btn" onClick={() => setZ((v) => Math.min(MAX_Z, v + 1))} disabled={z >= MAX_Z} aria-label="Zoom satellite image in" title="Zoom image in">+</button>
        </span>
      </div>
      <div
        ref={boxRef}
        className="ps-view"
        style={{ height }}
        role="img"
        aria-label={`Sentinel-2 cloudless mosaic ${year} around ${getPortName(code)}, zoom ${z}`}
      >
        {tiles.map((t) => (
          <img
            key={`${year}/${t.key}`}
            src={s2TileUrl(year, z, t.x, t.y)}
            alt=""
            draggable={false}
            loading="lazy"
            decoding="async"
            onError={() => setFailed((f) => f + 1)}
            style={{ left: t.left, top: t.top, width: TILE, height: TILE }}
          />
        ))}
        <span className="ps-cross" aria-hidden="true" />
        <span className="ps-scale" aria-hidden="true"><span style={{ width: bar.px }} />{bar.label}</span>
        <span className="ps-zoom" aria-hidden="true">z{z}{z > NATIVE_Z ? ' · upsampled' : ''}</span>
        {allFailed && <span className="ps-fail">Imagery did not load (EOX tile server unreachable).</span>}
      </div>
      <div className="ps-foot">
        {pw ? (
          <span className="ps-centre" role="group" aria-label="Centre the image on">
            Centre on
            <button type="button" aria-pressed={usePw} onClick={() => setCentre('portwatch')}>PortWatch port</button>
            <button type="button" aria-pressed={!usePw} onClick={() => setCentre('dataset')}>dataset point</button>
          </span>
        ) : null}
        <span>
          {lat.toFixed(3)}°, {lon.toFixed(3)}° · crosshair = {usePw
            ? `PortWatch "${pw.name}" (${pw.match}, ${pw.km_from_dataset} km from the dataset point)`
            : `dataset port point${loaded && !pw ? ' (no PortWatch match within 30 km)' : ''}`}
        </span>
        <span>
          <a href="https://cloudless.eox.at" target="_blank" rel="noreferrer">Sentinel-2 cloudless {year} by EOX</a>
          {' '}(contains modified Copernicus Sentinel data {year}) ·{' '}
          <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noreferrer">CC BY-NC-SA 4.0</a>
        </span>
      </div>
    </div>
  );
}
