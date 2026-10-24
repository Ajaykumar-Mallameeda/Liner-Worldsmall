/**
 * benchBaseline.js — the frozen 30-seed benchmark of one dataset, reduced to the means the headline
 * figures are compared against. Failed / unverified seeds are left out (benchStats.flagged).
 * Fetched once per dataset per page load; read-only.
 */

import { useEffect, useState } from 'react';
import { apiClient } from './apiClient.js';
import { num, stats, flagged, benchKeyFor } from '../utils/benchStats.js';

const cache = new Map();

function summarise(seeds) {
  const ok = seeds.filter((r) => !flagged(r));
  if (!ok.length) return null;
  const col = (f) => stats(ok.map(f).map(num));
  return {
    n: ok.length,
    excluded: seeds.length - ok.length,
    profit: col((r) => r.weekly_profit_usd),
    coverage: col((r) => r.coverage_pct),
    services: col((r) => r.services_operated),
    marginPct: col((r) => (r.profit_margin_on_revenue == null ? null : r.profit_margin_on_revenue * 100)),
    served: col((r) => r.served_teu),
    unserved: col((r) => r.unserved_teu),
    seeds: ok,
  };
}

export function loadBenchBaseline(datasetName) {
  const key = benchKeyFor(datasetName);
  if (!key) return Promise.resolve(null);
  if (!cache.has(key)) {
    cache.set(key, apiClient.getBenchmarkSeeds(key)
      .then((r) => { const s = summarise(r?.seeds || []); return s && { ...s, dataset: key }; })
      .catch(() => { cache.delete(key); return null; }));
  }
  return cache.get(key);
}

/** { n, excluded, profit, coverage, services, marginPct, served, unserved, seeds, dataset } or null while loading / unavailable. */
export function useBenchBaseline(datasetName) {
  const [base, setBase] = useState(null);
  useEffect(() => {
    let live = true;
    setBase(null);
    loadBenchBaseline(datasetName).then((b) => { if (live) setBase(b); });
    return () => { live = false; };
  }, [datasetName]);
  return base;
}
