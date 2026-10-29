/**
 * ecaZones — the SOx emission control areas (GET /api/eca/zones, backend/data/eca_zones.geojson), fetched once per
 * page when a map layer or the Emissions view asks for them.
 */
import { useEffect, useState } from 'react';

let cache = null;
let inflight = null;

function load() {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = fetch('/api/eca/zones')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => { cache = d; return d; })
      .finally(() => { inflight = null; });
  }
  return inflight;
}

export function useEcaZones(enabled = true) {
  const [state, setState] = useState(() => ({ status: cache ? 'ok' : 'idle', data: cache }));
  useEffect(() => {
    if (!enabled || cache) { if (cache) setState({ status: 'ok', data: cache }); return undefined; }
    let live = true;
    setState({ status: 'loading', data: null });
    load().then((d) => live && setState({ status: 'ok', data: d }))
      .catch(() => live && setState({ status: 'unavailable', data: null }));
    return () => { live = false; };
  }, [enabled]);
  return state;
}
