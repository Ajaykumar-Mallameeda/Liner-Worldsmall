/**
 * mapPrefsStore — the viewer's map choices, shared by every map surface and remembered in this browser.
 *
 *   engine      'gl' (MapLibre + deck.gl) | 'svg' (the classic SVG map; also used when WebGL2 is missing)
 *   projection  'mercator' (flat) | 'globe'
 *   basemap     a key of components/map/basemaps.js BASEMAPS
 *   layers      on/off per map layer (see LAYER_DEFS)
 *
 * localStorage is a convenience only: every read and write is guarded, and the defaults render without it.
 */
import { useSyncExternalStore } from 'react';

const KEY = 'liner.mapPrefs.v1';

/** Toggleable layers, grouped as in the layer panel. `motion: true` layers only animate at full motion. */
export const LAYER_DEFS = [
  { id: 'routes', group: 'Plan', label: 'Service legs', hint: 'One line per leg along its sea lane; width = TEU on the leg' },
  { id: 'ports', group: 'Plan', label: 'Ports', hint: 'Dataset ports; size = port calls by the plan, grey = not called' },
  { id: 'labels', group: 'Plan', label: 'Busiest port labels', hint: 'The ten most-called ports with their call counts' },
  { id: 'vessels', group: 'Plan', label: 'Vessels (replay clock)', hint: 'Every vessel of the services on screen at the timeline clock, from each service\'s leg schedule' },
  { id: 'hubs', group: 'Plan', label: 'Transshipment hubs', hint: 'Ports where routed cargo changes ship; ring area = TEU transferred there per week. Tooltip: transshipment cost and the busiest service connection' },
  { id: 'flows', group: 'Plan', label: 'Cargo flow particles', hint: 'Particles running along each leg in sailing direction; width = TEU. Full motion only', motion: true },
  { id: 'ais', group: 'Live', label: 'Live AIS vessels', hint: 'Real ships heard by AIS in the last hour, refreshed every minute (Digitraffic open data: Baltic Sea and approaches only; worldwide feeds need a paid key). Arrow = heading', default: false },
  { id: 'seastate', group: 'Weather', label: 'Sea state (forecast)', hint: 'Worst wave height forecast at points every 250 nm along the plan lanes over the next days, by WMO sea-state code (Open-Meteo Marine)', default: false },
  { id: 'currents', group: 'Weather', label: 'Ocean currents', hint: 'Mean forecast surface current at the same points (MeteoFrance SMOC via Open-Meteo); arrow = where it flows', default: false },
  { id: 'eca', group: 'Regulation', label: 'ECA zones (sulphur)', hint: 'SOx emission control areas: fuel ≤ 0.10% sulphur inside (Baltic, North Sea, North America, US Caribbean, Mediterranean since May 2025). Marine Regions polygons', default: false },
  { id: 'chokepoints', group: 'Risk', label: 'Chokepoints', hint: 'Straits and canals: size = TEU / week the plan carries through; tooltip adds real transit counts from IMF PortWatch' },
  { id: 'warrisk', group: 'Risk', label: 'War-risk areas (JWC)', hint: 'Joint War Committee listed areas (JWLA-035, 16 Sep 2026): a voyage inside needs an additional hull war premium. Tooltip gives the default rate per zone used by the What-if', default: false },
  { id: 'piracy', group: 'Risk', label: 'Piracy incidents (NGA ASAM)', hint: 'Anti-Shipping Activity Messages of the last 12 months from the US NGA (msi.nga.mil); shows an outage note when the service is down', default: false },
];

const DEFAULTS = {
  engine: 'gl',
  projection: 'mercator',
  basemap: 'vector',
  layers: Object.fromEntries(LAYER_DEFS.map((l) => [l.id, l.default !== false])),
};

function load() {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULTS;
    const p = JSON.parse(raw);
    return { ...DEFAULTS, ...p, layers: { ...DEFAULTS.layers, ...(p.layers || {}) } };
  } catch (_) {
    return DEFAULTS;
  }
}

let prefs = typeof window === 'undefined' ? DEFAULTS : load();
const listeners = new Set();

export const getMapPrefs = () => prefs;
export function setMapPrefs(patch) {
  prefs = { ...prefs, ...patch, layers: { ...prefs.layers, ...(patch.layers || {}) } };
  try { window.localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (_) { /* storage unavailable */ }
  listeners.forEach((fn) => fn());
}
export const toggleMapLayer = (id) => setMapPrefs({ layers: { [id]: !prefs.layers[id] } });
export function subscribeMapPrefs(fn) { listeners.add(fn); return () => listeners.delete(fn); }
export function useMapPrefs() { return useSyncExternalStore(subscribeMapPrefs, getMapPrefs, getMapPrefs); }
