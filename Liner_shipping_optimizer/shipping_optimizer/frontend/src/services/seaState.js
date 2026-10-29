/**
 * seaState — forecast sea state and currents along the plan's lanes (POST /api/weather/legs, backend/weather.py,
 * Open-Meteo Marine). One shared store: the Sea state & currents view and the map's Weather layers read the same
 * result, keyed by run and forecast window, so the forecast is fetched once.
 */
import { useEffect, useState } from 'react';
import { getSelectedRun, subscribeRun } from './runSelection.js';

const results = new Map();          // key -> { status, data, error }
const inflight = new Map();
const subs = new Set();
let lastKey = null;                 // what the map shows: the latest result asked for

const keyOf = (run, days) => JSON.stringify({ run, days });
const emit = () => subs.forEach((fn) => fn());

export function loadSeaState(run, days = 7) {
  const key = keyOf(run, days);
  lastKey = key;
  const have = results.get(key);
  if (have?.status === 'ok' || inflight.has(key)) { emit(); return; }
  results.set(key, { status: 'loading', data: null, error: null });
  emit();
  const p = fetch('/api/weather/legs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ run, forecast_days: days }) })
    .then(async (r) => {
      const b = await r.json().catch(() => null);
      if (!r.ok || !b) throw Object.assign(new Error(b?.detail || `HTTP ${r.status}`), { unavailable: !b });
      if (b.status === 'unavailable') throw new Error(`Open-Meteo unreachable: ${b.error || 'no data'}`);
      results.set(key, { status: 'ok', data: b, error: null });
    })
    .catch((e) => results.set(key, { status: e.unavailable ? 'unavailable' : 'error', data: null, error: String(e?.message || e) }))
    .finally(() => { inflight.delete(key); emit(); });
  inflight.set(key, p);
}

const idle = { status: 'idle', data: null, error: null };

/** The view: result for (run, days), loading it on first use. */
export function useSeaState(run, days, enabled = true) {
  const [, tick] = useState(0);
  useEffect(() => { const fn = () => tick((n) => n + 1); subs.add(fn); return () => subs.delete(fn); }, []);
  useEffect(() => { if (enabled) loadSeaState(run, days); }, [enabled, JSON.stringify(run), days]);
  return enabled ? results.get(keyOf(run, days)) || idle : idle;
}

/** The map: the latest result any view asked for, else the selected run's 7-day forecast. */
export function useMapSeaState(enabled) {
  const [, tick] = useState(0);
  useEffect(() => {
    if (!enabled) return undefined;
    const fn = () => tick((n) => n + 1);
    subs.add(fn);
    if (!lastKey) loadSeaState(getSelectedRun(), 7);
    const off = subscribeRun((run) => loadSeaState(run, 7));
    return () => { subs.delete(fn); off?.(); };
  }, [enabled]);
  return enabled && lastKey ? results.get(lastKey) || idle : idle;
}

// Risk by WMO sea-state code of the worst forecast wave height (backend/weather.py). One hue, darker = calmer, so
// the severe seas are the brightest marks on the dark map.
export const SEA_RISKS = [
  ['low', 'Low · up to 2.5 m (rough)', '#6b5a35'],
  ['moderate', 'Moderate · 2.5–4 m (very rough)', '#b7791f'],
  ['high', 'High · 4–6 m', '#f59e0b'],
  ['severe', 'Severe · over 6 m (very high+)', '#fde68a'],
];
export const seaRiskTone = (risk) => (SEA_RISKS.find(([k]) => k === risk) || SEA_RISKS[0])[2];
export const CURRENT_TONE = '#7dd3fc';
