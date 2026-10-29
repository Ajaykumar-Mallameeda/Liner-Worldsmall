/**
 * warRisk — JWC listed areas (GET /api/war-risk/areas, backend/war_risk.py: JWLA-035 polygons, rate zones and their
 * default premiums) and NGA ASAM piracy incidents of the last 12 months (GET /api/war-risk/piracy), fetched once per
 * page when a map layer asks for them.
 */
import { useEffect, useState } from 'react';

const store = { areas: null, piracy: null };
const inflight = {};

function load(key, url, shape) {
  if (store[key]) return Promise.resolve(store[key]);
  if (!inflight[key]) {
    inflight[key] = fetch(url)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => { store[key] = shape(d); return store[key]; })
      .finally(() => { delete inflight[key]; });
  }
  return inflight[key];
}

/** The areas as a GeoJSON FeatureCollection; each feature carries its rate zones with default premiums. */
export function areasGeoJson(d) {
  return {
    type: 'FeatureCollection',
    features: d.areas.map((a) => ({
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [[...a.polygon, a.polygon[0]]] },
      properties: { id: a.id, label: a.label, drawn: a.drawn, zones: d.zones.filter((z) => z.area === a.id) },
    })),
    circular: d.circular, namedCountries: d.named_countries, namedCall: d.named_call,
  };
}

function useLoaded(key, url, shape, enabled) {
  const [state, setState] = useState(() => ({ status: store[key] ? 'ok' : 'idle', data: store[key] }));
  useEffect(() => {
    if (!enabled) return undefined;
    if (store[key]) { setState({ status: 'ok', data: store[key] }); return undefined; }
    let live = true;
    setState({ status: 'loading', data: null });
    load(key, url, shape).then((d) => live && setState({ status: 'ok', data: d }))
      .catch(() => live && setState({ status: 'unavailable', data: null }));
    return () => { live = false; };
  }, [enabled]); // eslint-disable-line react-hooks/exhaustive-deps
  return state;
}

export const useWarRiskAreas = (enabled = true) => useLoaded('areas', '/api/war-risk/areas', areasGeoJson, enabled);
export const usePiracy = (enabled = true) => useLoaded('piracy', '/api/war-risk/piracy?days=365', (d) => d, enabled);
