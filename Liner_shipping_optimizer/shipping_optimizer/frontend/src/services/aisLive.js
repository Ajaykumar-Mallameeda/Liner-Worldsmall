/**
 * aisLive — live AIS positions for the map layer (GET /api/ais/live, backend/ais.py: Digitraffic, Baltic coverage).
 * Polls once a minute while a map has the layer on; one shared poll however many maps are mounted.
 */
import { useEffect, useState } from 'react';

const POLL_MS = 60_000;
let last = { status: 'idle', data: null, error: null };
const subs = new Set();
let timer = null;

async function poll() {
  if (last.status !== 'ok') emit({ ...last, status: 'loading' });
  try {
    const r = await fetch('/api/ais/live');
    const b = await r.json().catch(() => null);
    if (!r.ok || !b?.vessels) throw new Error(b?.detail || `HTTP ${r.status}`);
    emit({ status: 'ok', data: b, error: null });
  } catch (e) {
    emit({ status: last.data ? 'ok' : 'unavailable', data: last.data, error: String(e?.message || e) });
  }
}

function emit(s) { last = s; subs.forEach((fn) => fn(s)); }

export const AIS_CATEGORIES = [
  ['cargo', 'Cargo (AIS 70-79)', '#38bdf8'],
  ['tanker', 'Tanker', '#f59e0b'],
  ['passenger', 'Passenger', '#a78bfa'],
  ['other', 'Other / service / tug', '#64748b'],
];
export const aisTone = (cat) => (AIS_CATEGORIES.find(([k]) => k === cat) || AIS_CATEGORIES[3])[2];

export function useAisLive(enabled) {
  const [s, setS] = useState(last);
  useEffect(() => {
    if (!enabled) return undefined;
    subs.add(setS);
    if (!timer) { poll(); timer = setInterval(poll, POLL_MS); }
    setS(last);
    return () => {
      subs.delete(setS);
      if (!subs.size && timer) { clearInterval(timer); timer = null; }
    };
  }, [enabled]);
  return enabled ? s : { status: 'idle', data: null, error: null };
}
