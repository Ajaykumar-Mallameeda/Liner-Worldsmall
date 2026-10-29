/**
 * chokepoints.js — the plan's exposure to straits and canals, real traffic through them, and the resilience
 * ranking (backend/chokepoints.py).
 *
 *   useChokepointExposure(run)  POST /api/chokepoints/exposure: TEU / week the plan carries through each passage
 *   usePortWatch()              GET  /api/chokepoints/portwatch: IMF PortWatch transit calls, last 30 days vs a year ago
 *   fetchResilience(run, target, limit)  POST /api/resilience: single closures ranked by weekly profit lost
 *
 * Results are kept per run in this module, so every map surface shares one request.
 */
import { useEffect, useState } from 'react';
import { runKey } from './runSelection.js';

/** searoute passage id → where to draw it (kept in step with backend/chokepoints.py CHOKEPOINTS). */
export const CHOKEPOINT_AT = {
  suez: { name: 'Suez Canal', at: [32.35, 30.6] },
  panama: { name: 'Panama Canal', at: [-79.7, 9.1] },
  bosporus: { name: 'Bosporus', at: [29.05, 41.12] },
  babalmandab: { name: 'Bab-el-Mandeb', at: [43.4, 12.6] },
  malacca: { name: 'Strait of Malacca', at: [100.8, 2.6] },
  ormuz: { name: 'Strait of Hormuz', at: [56.4, 26.5] },
  south_africa: { name: 'Cape of Good Hope', at: [18.5, -34.8] },
  gibraltar: { name: 'Strait of Gibraltar', at: [-5.6, 35.95] },
  sunda: { name: 'Sunda Strait', at: [105.8, -6.0] },
  chili: { name: 'Strait of Magellan', at: [-70.6, -53.4] },
};

const exposureCache = new Map();   // runKey → Promise<body | null>
let portwatchPromise = null;

async function postJson(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error(j?.detail || `HTTP ${r.status}`);
  return j;
}

/** { status: 'loading' | 'ok' | 'unavailable', data } for the run's exposure. */
export function useChokepointExposure(run) {
  const key = run ? runKey(run) : null;
  const [state, setState] = useState({ status: 'loading', data: null });
  useEffect(() => {
    if (!key) return undefined;
    let off = false;
    if (!exposureCache.has(key)) exposureCache.set(key, postJson('/api/chokepoints/exposure', { run }).catch(() => { exposureCache.delete(key); return null; }));
    exposureCache.get(key).then((data) => { if (!off) setState({ status: data ? 'ok' : 'unavailable', data }); });
    return () => { off = true; };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return state;
}

/** { status, data } of the PortWatch summary (one request per page load; the backend caches 12 h). */
export function usePortWatch(enabled = true) {
  const [state, setState] = useState({ status: 'loading', data: null });
  useEffect(() => {
    if (!enabled) return undefined;
    let off = false;
    if (!portwatchPromise) {
      portwatchPromise = fetch('/api/chokepoints/portwatch').then((r) => (r.ok ? r.json() : null)).catch(() => null)
        .then((d) => { if (!d) portwatchPromise = null; return d; });
    }
    portwatchPromise.then((data) => { if (!off) setState({ status: data ? 'ok' : 'unavailable', data }); });
    return () => { off = true; };
  }, [enabled]);
  return state;
}

export const fetchResilience = (run, target = 'passages', limit = 25) => postJson('/api/resilience', { run, target, limit });

/** Percent change of the last 30 days against the same 30 days a year earlier (null when either is missing). */
export function yoyPct(now, before) {
  if (now == null || before == null || before === 0) return null;
  return ((now - before) / before) * 100;
}

/** The passages a re-routed leg's detour sails through that the original leg did not. */
export const addedPassages = (leg) => (leg.via_after || []).filter((p) => !(leg.via_before || []).includes(p));
