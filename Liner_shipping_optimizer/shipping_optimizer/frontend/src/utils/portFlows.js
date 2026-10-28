/**
 * portFlows.js — what the plan does at each port, from the run's routed flows (network_ledger.plan.flows)
 * and the dataset's lane demand (the engine's canonical problem file, /api/datasets/<dataset>/demand).
 *
 *   served(o→d)    = Σ TEU of the flows from o to d
 *   unserved(o→d)  = demand(o→d) − served(o→d), never below 0
 *
 * Summed over lanes this reproduces the ledger's served / unserved totals exactly (checked on WorldSmall:
 * 153,078 TEU unserved both ways); `portActivity` returns both so the screen can show the check.
 */

const demandCache = new Map();

/** Lane demand + port tariffs of a dataset (cached per dataset; null when the backend is not reachable). */
export function fetchDemand(dataset) {
  const key = String(dataset || 'worldsmall');
  if (!demandCache.has(key)) {
    demandCache.set(key, fetch(`/api/datasets/${encodeURIComponent(key)}/demand`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null)
      .then((d) => { if (!d) demandCache.delete(key); return d; }));
  }
  return demandCache.get(key);
}

/**
 * The ledger whose plan is exactly `services` (same service ids): the run's top-level ledger or one of its
 * iterations' (each iteration_results entry carries its own). null when none matches, so the caller never
 * pairs services with another plan's flows.
 */
export function ledgerForServices(runtime, services) {
  const raw = runtime?.raw || runtime || {};
  const ids = (list) => (list || []).map((s) => String(s.id)).sort().join('|');
  const want = ids(services);
  if (!want) return null;
  const ledgers = [raw.network_ledger, ...(raw.iteration_results || []).map((it) => it?.network_ledger)];
  return ledgers.find((l) => l?.plan?.flows?.length && ids(l.plan.services) === want) || null;
}

/** The dataset a runtime belongs to (dataset_run, top level or inside test_scorecard; WorldSmall before that). */
export function datasetOf(runtime) {
  const raw = runtime?.raw || runtime || {};
  return runtime?.source?.dataset || raw?.dataset_run?.dataset || raw?.test_scorecard?.dataset_run?.dataset
    || (runtime?.source?.run?.kind === 'benchmark' ? runtime.source.run.dataset : 'WorldSmall');
}

const blank = (code) => ({
  code, exportTeu: 0, importTeu: 0, transshipTeu: 0, demandOut: 0, demandIn: 0, unservedOut: 0, unservedIn: 0,
  services: [], callsPerWeek: 0, lanesOut: new Map(), unservedLanes: [],
});

/**
 * Per-port activity. `services` are the plan's services (ports, frequency_per_week); `demand` the lane list
 * [[o, d, teu], ...] or null (then demand / unserved fields stay 0 and `hasDemand` is false).
 */
export function portActivity({ flows = [], services = [], demand = null }) {
  const ports = new Map();
  const at = (c) => { if (!ports.has(c)) ports.set(c, blank(c)); return ports.get(c); };
  const served = new Map();
  let servedTotal = 0;
  flows.forEach((f) => {
    const teu = Number(f.teu) || 0;
    if (teu <= 0) return;
    const k = `${f.origin}|${f.destination}`;
    served.set(k, (served.get(k) || 0) + teu);
    servedTotal += teu;
    const o = at(f.origin); const d = at(f.destination);
    o.exportTeu += teu; d.importTeu += teu;
    o.lanesOut.set(f.destination, (o.lanesOut.get(f.destination) || 0) + teu);
    (f.segments || []).slice(0, -1).forEach((seg) => { at(seg[2]).transshipTeu += teu; });
  });
  services.forEach((s) => {
    const f = Number(s.frequency_per_week) || 1;
    new Set(s.ports || []).forEach((p) => {
      const e = at(p);
      e.services.push(s);
      e.callsPerWeek += f;
    });
  });
  const lanes = [];
  let demandTotal = 0; let unservedTotal = 0;
  (demand || []).forEach(([o, d, teu]) => {
    const t = Number(teu) || 0;
    const u = Math.max(0, t - (served.get(`${o}|${d}`) || 0));
    demandTotal += t; unservedTotal += u;
    const po = at(o); const pd = at(d);
    po.demandOut += t; pd.demandIn += t;
    if (u > 0) {
      po.unservedOut += u; pd.unservedIn += u;
      const lane = { o, d, teu: u, demand: t };
      lanes.push(lane);
      po.unservedLanes.push(lane); pd.unservedLanes.push(lane);
    }
  });
  lanes.sort((a, b) => b.teu - a.teu);
  ports.forEach((p) => p.unservedLanes.sort((a, b) => b.teu - a.teu));
  const maxUnserved = Math.max(0, ...[...ports.values()].map((p) => p.unservedOut + p.unservedIn));
  return { ports, lanes, maxUnserved, hasDemand: Boolean(demand), totals: { demand: demandTotal, served: servedTotal, unserved: unservedTotal } };
}
