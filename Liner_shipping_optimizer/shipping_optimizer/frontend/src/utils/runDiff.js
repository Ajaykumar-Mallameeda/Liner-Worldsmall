/**
 * runDiff.js — compare two plans (a run's final plan or one of its iterations).
 *
 * A plan is { services: selected_services rows, ledger: network_ledger } taken from a pipeline_output.json.
 * Services are matched by what they are, not by id (ids are reissued every run):
 *   1. same rotation and vessel class           → "kept" (or "retimed" when weekly departures differ)
 *   2. then same rotation, other vessel class   → "changed"
 *   3. the rest                                 → "removed" (only in A) / "added" (only in B)
 * A rotation is the closed port loop, compared from its alphabetically first port so that a loop listed
 * from another starting port still matches.
 */

import { transshipmentModel } from './transshipment.js';

/** Canonical form of a closed loop: rotated to start at its smallest port code (direction kept). */
export function rotationKey(ports) {
  const p = (ports || []).filter(Boolean);
  if (!p.length) return '';
  let best = null;
  for (let i = 0; i < p.length; i++) {
    const rot = [...p.slice(i), ...p.slice(0, i)].join('>');
    if (best === null || rot < best) best = rot;
  }
  return best;
}

/** The plan of a pipeline_output: iteration null = the run's own (top-level) plan. */
export function planOf(raw, iteration = null) {
  if (!raw) return null;
  if (iteration == null) return { services: raw.selected_services || [], ledger: raw.network_ledger || null };
  const it = (raw.iteration_results || []).find((x, i) => (x?.iteration ?? i) === iteration);
  return it ? { services: it.selected_services || [], ledger: it.network_ledger || null } : null;
}

export function planKpis(plan) {
  const wk = plan?.ledger?.weekly_usd || {};
  const dm = plan?.ledger?.demand_teu_per_week || {};
  const fleet = plan?.ledger?.fleet_by_class || {};
  const services = plan?.services || [];
  const vessels = Object.values(fleet).reduce((a, c) => a + (Number(c?.used) || 0), 0)
    || services.reduce((a, s) => a + (Number(s.vessels) || 0), 0);
  const flows = plan?.ledger?.plan?.flows;
  const ts = flows?.length ? transshipmentModel({ flows }).totals : null;
  return {
    transship_teu: ts ? ts.transferTeu : null,
    transship_share: ts ? ts.share : null,
    transship_hubs: ts ? ts.hubs : null,
    profit: wk.operating_profit ?? null,
    revenue: wk.revenue ?? null,
    cost: wk.total_operating_cost ?? null,
    fuel: wk.fuel_cost ?? null,
    vessel_cost: wk.vessel_cost ?? null,
    port_call_cost: wk.port_call_fixed_cost ?? null,
    handling: wk.handling_cost ?? null,
    transshipment: wk.transshipment_cost ?? null,
    margin_pct: wk.profit_margin_on_revenue != null ? wk.profit_margin_on_revenue * 100 : null,
    coverage_pct: dm.coverage_pct ?? null,
    served_teu: dm.served ?? null,
    services: services.length,
    departures: services.reduce((a, s) => a + (Number(s.frequency_per_week) || 0), 0),
    vessels: vessels || null,
  };
}

export function diffPlans(a, b) {
  const rows = [];
  const left = (a?.services || []).map((s) => ({ s, rot: rotationKey(s.ports), cls: s.vessel_class || '' }));
  const right = (b?.services || []).map((s) => ({ s, rot: rotationKey(s.ports), cls: s.vessel_class || '' }));
  const take = (pred) => {
    for (const x of left) {
      if (x.done) continue;
      const y = right.find((r) => !r.done && pred(x, r));
      if (!y) continue;
      x.done = true; y.done = true;
      const fa = Number(x.s.frequency_per_week) || 0; const fb = Number(y.s.frequency_per_week) || 0;
      const status = x.cls !== y.cls ? 'changed' : fa !== fb ? 'retimed' : 'kept';
      rows.push({ status, a: x.s, b: y.s, rot: y.rot });
    }
  };
  take((x, y) => x.rot === y.rot && x.cls === y.cls);
  take((x, y) => x.rot === y.rot);
  left.filter((x) => !x.done).forEach((x) => rows.push({ status: 'removed', a: x.s, b: null, rot: x.rot }));
  right.filter((y) => !y.done).forEach((y) => rows.push({ status: 'added', a: null, b: y.s, rot: y.rot }));
  const profit = (s) => (s && s.weekly_profit != null ? Number(s.weekly_profit) : null);
  rows.forEach((r) => {
    const pa = profit(r.a); const pb = profit(r.b);
    r.dProfit = (pb ?? 0) - (pa ?? 0);
  });
  const counts = rows.reduce((m, r) => ({ ...m, [r.status]: (m[r.status] || 0) + 1 }), {});
  return { rows, counts };
}

/**
 * Services for the map overlay and the id → status map WorldMap's `diff` prop reads. Ids are prefixed
 * (A: / B:) because the two runs reuse ids for different services. Matched services are drawn once, from B.
 */
export function diffOverlay(rows) {
  const services = []; const status = new Map();
  rows.forEach((r) => {
    const src = r.b || r.a;
    const id = `${r.b ? 'B' : 'A'}:${src.id}`;
    services.push({ ...src, id, region: src.region || 'world', load: Number(src.load) || 0 });
    status.set(id, r.status === 'added' ? 'added' : r.status === 'removed' ? 'removed' : 'kept');
  });
  return { services, status };
}

/**
 * One side of the split-screen diff (design D7): plan A's services (those only in A marked 'removed') or plan B's
 * (those only in B marked 'added'); matched services are 'kept' on both maps. fitPorts = every port of A and B, so
 * both maps frame the same area before the viewer moves them.
 */
export function diffSide(rows, side) {
  const key = side === 'A' ? 'a' : 'b';
  const services = []; const status = new Map(); const ports = new Set();
  rows.forEach((r) => {
    [r.a, r.b].forEach((sv) => (sv?.ports || []).forEach((p) => ports.add(p)));
    const src = r[key];
    if (!src) return;
    const id = `${side}:${src.id}`;
    services.push({ ...src, id, region: src.region || 'world', load: Number(src.load) || 0 });
    status.set(id, r.status === 'added' ? 'added' : r.status === 'removed' ? 'removed' : 'kept');
  });
  return { services, status, fitPorts: [...ports].sort() };
}
