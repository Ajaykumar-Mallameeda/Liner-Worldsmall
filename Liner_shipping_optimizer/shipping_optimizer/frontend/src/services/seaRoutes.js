/**
 * seaRoutes.js — the path each leg is drawn along.
 *
 * With the backend: real sea lanes from GET /api/searoutes/<dataset> (searoute / Eurostat maritime network;
 * visualisation only, not navigation), with the route's length, the passages it uses and the optimizer's own
 * LINERLIB distance for comparison. Without it: a great-circle path, labelled `source: 'great-circle'` so
 * the screen never presents it as a sea lane.
 *
 * Routes are cached per (dataset, avoid set, pair); `useSeaRoutes` batches the pairs a view needs.
 */
import { useEffect, useMemo, useState } from 'react';
import { geoInterpolate, geoDistance } from 'd3-geo';

const cache = new Map();            // `${ds}|${avoid}|${a}|${b}` → route
const inflight = new Map();         // `${ds}|${avoid}` → Promise
let backendDown = false;
const EARTH_NM = 3440.065;
const BATCH = 600;

/** Longitudes unwrapped so a path never jumps across ±180 (MapLibre / deck draw it continuously). */
export function unwrapPath(coords) {
  const out = []; let shift = 0;
  coords.forEach(([lon, lat], i) => {
    if (i) {
      const d = lon - coords[i - 1][0];
      if (d > 180) shift -= 360; else if (d < -180) shift += 360;
    }
    out.push([lon + shift, lat]);
  });
  return out;
}

/** Great-circle path between two [lon, lat] points (fallback when no sea lane is available). */
export function greatCircle(a, b, steps = 48) {
  const f = geoInterpolate(a, b);
  const pts = Array.from({ length: steps + 1 }, (_, i) => f(i / steps));
  return unwrapPath(pts);
}

export function greatCircleRoute(a, b) {
  return { coords: greatCircle(a, b), nm: geoDistance(a, b) * EARTH_NM, model_nm: null, passages: [], model_canal: null, source: 'great-circle' };
}

/** searoute passage ids → names shown on screen. */
export const PASSAGE_NAMES = {
  suez: 'Suez Canal',
  panama: 'Panama Canal',
  malacca: 'Strait of Malacca',
  babalmandab: 'Bab-el-Mandeb',
  gibraltar: 'Strait of Gibraltar',
  ormuz: 'Strait of Hormuz',
  bosporus: 'Bosporus',
  sunda: 'Sunda Strait',
  chili: 'Strait of Magellan',
  south_africa: 'Cape of Good Hope',
  northwest: 'Northwest Passage',
  bering: 'Bering Strait',
};
export const passageName = (id) => PASSAGE_NAMES[id] || id;

const keyOf = (ds, avoid, a, b) => `${String(ds).toLowerCase()}|${avoid}|${a}|${b}`;

async function fetchBatch(ds, avoid, pairs) {
  const qs = new URLSearchParams({ pairs: pairs.map(([a, b]) => `${a}-${b}`).join(',') });
  if (avoid) qs.set('avoid', avoid);
  const r = await fetch(`/api/searoutes/${encodeURIComponent(ds)}?${qs}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = await r.json();
  Object.entries(body.routes || {}).forEach(([k, v]) => {
    const [a, b] = k.split('|');
    cache.set(keyOf(ds, avoid, a, b), { ...v, source: 'searoute' });
  });
  return body;
}

/**
 * Sea routes for `pairs` ([[from, to], ...]) of `dataset`. `coordsOf(port)` → [lon, lat] for the fallback.
 * Returns { routes: Map("A|B" → route), status: 'loading' | 'searoute' | 'great-circle' | 'mixed' }.
 */
export function useSeaRoutes(dataset, pairs, coordsOf, avoid = '') {
  const want = useMemo(() => {
    const seen = new Set(); const out = [];
    (pairs || []).forEach(([a, b]) => { const k = `${a}|${b}`; if (a && b && a !== b && !seen.has(k)) { seen.add(k); out.push([a, b]); } });
    return out;
  }, [pairs]);
  const sig = `${dataset}|${avoid}|${want.map((p) => p.join('-')).join(',')}`;
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!dataset || !want.length || backendDown) return undefined;
    const missing = want.filter(([a, b]) => !cache.has(keyOf(dataset, avoid, a, b)));
    if (!missing.length) return undefined;
    let off = false;
    (async () => {
      for (let i = 0; i < missing.length; i += BATCH) {
        try { await fetchBatch(dataset, avoid, missing.slice(i, i + BATCH)); }
        catch (_) { backendDown = true; break; }
      }
      if (!off) setTick((t) => t + 1);
    })();
    return () => { off = true; };
  }, [sig]); // eslint-disable-line react-hooks/exhaustive-deps

  return useMemo(() => {
    const routes = new Map(); let sea = 0; let gc = 0; let pending = 0;
    want.forEach(([a, b]) => {
      const hit = cache.get(keyOf(dataset, avoid, a, b));
      if (hit) { routes.set(`${a}|${b}`, hit); sea++; return; }
      const pa = coordsOf(a); const pb = coordsOf(b);
      if (!pa || !pb) return;
      if (!backendDown) pending++;
      routes.set(`${a}|${b}`, greatCircleRoute(pa, pb)); gc++;
    });
    const status = pending ? 'loading' : !gc ? 'searoute' : !sea ? 'great-circle' : 'mixed';
    return { routes, status };
  }, [sig, tick, coordsOf]); // eslint-disable-line react-hooks/exhaustive-deps
}

/**
 * Extra vertices so no segment is longer than `maxDeg` degrees. On the globe a path segment is a straight chord;
 * long ones (sea lanes are simplified across open ocean) would cut through the sphere and vanish in places.
 */
export function densify(coords, maxDeg = 2) {
  if (!coords || coords.length < 2) return coords;
  const out = [coords[0]];
  for (let i = 1; i < coords.length; i++) {
    const [x0, y0] = coords[i - 1]; const [x1, y1] = coords[i];
    const n = Math.ceil(Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) / maxDeg);
    for (let k = 1; k < n; k++) out.push([x0 + ((x1 - x0) * k) / n, y0 + ((y1 - y0) * k) / n]);
    out.push(coords[i]);
  }
  return out;
}

/** Cumulative length (in degrees-ish screen units) along a path, for placing points by fraction. */
export function pathMeasure(coords) {
  const cum = [0];
  for (let i = 1; i < coords.length; i++) {
    const dx = coords[i][0] - coords[i - 1][0]; const dy = coords[i][1] - coords[i - 1][1];
    cum.push(cum[i - 1] + Math.hypot(dx * Math.cos(((coords[i][1] + coords[i - 1][1]) / 2) * Math.PI / 180), dy));
  }
  return cum;
}

/** Point and heading (degrees, 0 = east, counter-clockwise) at fraction t (0..1) along a path. */
export function pointAlong(coords, cum, t) {
  const total = cum[cum.length - 1] || 1;
  const target = Math.max(0, Math.min(1, t)) * total;
  let i = 1;
  while (i < cum.length - 1 && cum[i] < target) i++;
  const seg = cum[i] - cum[i - 1] || 1;
  const f = (target - cum[i - 1]) / seg;
  const a = coords[i - 1]; const b = coords[i] || a;
  const p = [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
  const heading = Math.atan2(b[1] - a[1], (b[0] - a[0]) * Math.cos(p[1] * Math.PI / 180)) * 180 / Math.PI;
  return { p, heading };
}

/** [[west, south], [east, north]] around [lon, lat] points, across the antimeridian when that is tighter; null = world. */
export function boundsOf(points) {
  if (!points.length) return null;
  const lons = points.map((p) => p[0]).sort((a, b) => a - b);
  const lats = points.map((p) => p[1]);
  let gap = lons[0] + 360 - lons[lons.length - 1]; let west = lons[0]; let east = lons[lons.length - 1];
  for (let i = 1; i < lons.length; i++) {
    if (lons[i] - lons[i - 1] > gap) { gap = lons[i] - lons[i - 1]; west = lons[i]; east = lons[i - 1] + 360; }
  }
  if (east - west > 250) return null;
  const pad = points.length === 1 ? 4 : 0;
  return [[west - pad, Math.min(...lats) - pad], [east + pad, Math.max(...lats) + pad]];
}
