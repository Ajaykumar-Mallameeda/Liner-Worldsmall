/**
 * portLocate.js
 * -------------
 * Where a port is for the satellite views (#9 Sentinel-2, #10 Sentinel-1): IMF PortWatch's point when the backend
 * matches one (/api/ports/locate: UN/LOCODE, else nearest within 30 km of the dataset point), else the dataset's
 * own point. One request per port, shared by every component that asks.
 */

import { useEffect, useState } from 'react';
import { getPortCoordinates } from '../utils/portLookup.js';

const cache = new Map(); // code -> Promise<{ portwatch } | null>

export function locatePort(code) {
  const ds = getPortCoordinates(code);
  if (!ds) return Promise.resolve(null);
  if (!cache.has(code)) {
    const q = new URLSearchParams({ code, lat: String(ds[1]), lon: String(ds[0]) });
    cache.set(code, fetch(`/api/ports/locate?${q}`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null)
      .then((j) => {
        if (!j) cache.delete(code); // retry next time the backend may be up
        return { portwatch: j?.portwatch || null, reachable: Boolean(j) };
      }));
  }
  return cache.get(code);
}

/** { dataset: [lon, lat] | null, portwatch: {...} | null, loaded } for a port code. */
export function usePortLocation(code) {
  const [state, setState] = useState({ code: null, portwatch: null, loaded: false });
  useEffect(() => {
    let live = true;
    locatePort(code).then((r) => { if (live) setState({ code, portwatch: r?.portwatch || null, loaded: true }); });
    return () => { live = false; };
  }, [code]);
  const mine = state.code === code;
  return { dataset: getPortCoordinates(code), portwatch: mine ? state.portwatch : null, loaded: mine && state.loaded };
}
