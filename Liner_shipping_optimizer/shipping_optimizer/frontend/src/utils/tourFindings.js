/**
 * tourFindings.js — the key findings presentation mode points at on each slide (design D11, guided tour).
 * Pure: every sentence is computed from the run on screen (runtime.global / regions, the selected services) and,
 * when loaded, the 30-seed benchmark baseline. A finding names the panel it belongs to (the panel's aria-label,
 * matched by prefix) so the callout can point at it; a finding whose numbers are missing is left out.
 */

import { ledgerForServices } from './portFlows.js';
import { transshipmentModel } from './transshipment.js';

const usd = (v) => {
  const a = Math.abs(v);
  const s = a >= 1e9 ? `$${(a / 1e9).toFixed(2)}B` : a >= 1e6 ? `$${(a / 1e6).toFixed(1)}M` : a >= 1e3 ? `$${Math.round(a / 1e3)}K` : `$${Math.round(a)}`;
  return v < 0 ? `−${s}` : s;
};
const int = (v) => Math.round(v).toLocaleString('en-US');
const ok = (v) => v != null && Number.isFinite(Number(v));
const n = (v) => Number(v);

export function tourFindings(runtime, bench = null) {
  const g = runtime?.global || {};
  const svcs = (g.selected_services || []).filter((s) => s && s.id != null);
  const regions = Object.values(runtime?.regions || {});
  const out = {};
  const add = (tab, panel, title, text) => { if (text) (out[tab] ||= []).push({ panel, title, text }); };

  // Overview
  if (ok(g.weeklyProfit) && ok(g.revenue)) {
    const vs = bench?.profit?.mean != null ? `; ${n(g.weeklyProfit) >= bench.profit.mean ? 'above' : 'below'} the ${bench.n}-seed mean of ${usd(bench.profit.mean)}` : '';
    add('command_center', 'Current Decision', 'Weekly result', `${usd(g.weeklyProfit)} profit on ${usd(g.revenue)} revenue (${(n(g.weeklyProfit) / n(g.revenue) * 100).toFixed(1)}% margin)${vs}.`);
  }
  const costs = [['Fuel', g.fuelCost], ['Port calls and handling', g.portCost], ['Transshipment', g.transshipCost]].filter(([, v]) => ok(v) && n(v) > 0);
  const total = ok(g.totalCost) ? n(g.totalCost) : ok(g.operatingCost) ? n(g.operatingCost) : null;
  if (costs.length && total) {
    const [name, v] = costs.sort((a, b) => n(b[1]) - n(a[1]))[0];
    add('command_center', 'Revenue to Profit', 'Largest cost', `${name}: ${usd(v)} a week, ${(n(v) / total * 100).toFixed(0)}% of the ${usd(total)} cost.`);
  }
  if (svcs.length) {
    const ports = new Set(svcs.flatMap((s) => s.ports || []));
    add('command_center', 'Network Intelligence', 'The network', `${svcs.length} services call ${ports.size} ports, ${int(svcs.reduce((t, sv) => t + n(sv.frequency_per_week || 0), 0))} departures a week.`);
  }

  // Network
  if (svcs.length) {
    const byProfit = [...svcs].filter((s) => ok(s.weekly_profit)).sort((a, b) => n(b.weekly_profit) - n(a.weekly_profit));
    const losers = byProfit.filter((s) => n(s.weekly_profit) < 0);
    if (byProfit.length) {
      const top = byProfit[0];
      add('network_intel', 'Selected Services', 'Services', `Most profitable: ${top.id}, ${usd(top.weekly_profit)} a week. ${losers.length ? `${losers.length} lose money (${usd(losers.reduce((a, s) => a + n(s.weekly_profit), 0))} together).` : 'None loses money.'}`);
    }
    const calls = new Map();
    svcs.forEach((s) => new Set(s.ports || []).forEach((p) => calls.set(p, (calls.get(p) || 0) + 1)));
    const [hub, k] = [...calls.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0] || [];
    if (hub) add('network_intel', 'Network Canvas', 'Busiest port', `${hub} is called by ${k} of the ${svcs.length} services.`);
  }

  // Transshipment (the plan's own ledger flows; cost = the ledger's line)
  const ledger = svcs.length ? ledgerForServices(runtime, svcs) : null;
  if (ledger) {
    const tm = transshipmentModel({ flows: ledger.plan.flows });
    const cost = ledger.weekly_usd?.transshipment_cost;
    if (tm.totals.transferTeu > 0) {
      const top = tm.hubs.slice(0, 3).map((h) => h.code).join(', ');
      add('transshipment', 'Transfer hubs', 'Transshipment', `${int(tm.totals.transferTeu)} TEU a week (${tm.totals.share.toFixed(1)}% of cargo carried) changes ship at ${tm.totals.hubs} hubs${ok(cost) ? `, costing ${usd(cost)} a week` : ''}; ${top} handle ${tm.totals.top3Share.toFixed(0)}% of the transfers.`);
    }
  }

  // Demand
  if (ok(g.coverage) && ok(g.weeklyDemand)) {
    const unserved = ok(g.unserved) ? n(g.unserved) : n(g.weeklyDemand) * (1 - n(g.coverage) / 100);
    add('demand_intel', 'Coverage', 'Coverage', `${n(g.coverage).toFixed(1)}% of ${int(g.weeklyDemand)} TEU a week is carried; ${int(unserved)} TEU a week is not carried.`);
  }
  const regCov = regions.filter((r) => ok(r.coverage)).sort((a, b) => n(a.coverage) - n(b.coverage));
  if (regCov.length > 1) {
    const lo = regCov[0]; const hi = regCov[regCov.length - 1];
    add('demand_intel', 'Regional Demand', 'Regions', `Lowest coverage: ${lo.name} at ${n(lo.coverage).toFixed(1)}%; highest: ${hi.name} at ${n(hi.coverage).toFixed(1)}%.`);
  }

  // Ports
  if (svcs.length) {
    const calls = new Map();
    svcs.forEach((s) => (s.ports || []).forEach((p) => calls.set(p, (calls.get(p) || 0) + n(s.frequency_per_week || 1))));
    const top = [...calls.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 3);
    if (top.length) add('port_intel', 'Busiest Ports', 'Busiest ports', `${top.map(([p, c]) => `${p} (${int(c)} calls a week)`).join(', ')}.`);
  }

  // Fleet
  if (svcs.length) {
    const cls = new Map();
    svcs.forEach((s) => { if (s.vessel_class) cls.set(s.vessel_class, (cls.get(s.vessel_class) || 0) + n(s.vessels || 0)); });
    const [c, v] = [...cls.entries()].sort((a, b) => b[1] - a[1])[0] || [];
    const vessels = svcs.reduce((a, s) => a + n(s.vessels || 0), 0);
    if (c && vessels) add('fleet_intel', 'Vessel Class Mix', 'Fleet', `The run's ledger deploys ${int(vessels)} vessels (round trip × weekly frequency); ${c} is the largest class with ${int(v)} (${(v / vessels * 100).toFixed(0)}%).`);
    const lf = svcs.filter((s) => ok(s.leg_load_factor));
    if (lf.length) {
      const full = lf.filter((s) => n(s.leg_load_factor) >= 0.9).length;
      const mean = lf.reduce((a, s) => a + n(s.leg_load_factor), 0) / lf.length;
      add('fleet_intel', 'Leg Load Factor', 'Load', `Average leg load ${(mean * 100).toFixed(0)}%; ${full} of ${lf.length} services run 90% full or more.`);
    }
  }

  // Decision
  const iters = runtime?.iterations || [];
  if (iters.length) {
    const sel = g.selected_iteration ?? g.iter;
    add('decision_center', 'Iteration Overview', 'Decision', `${iters.length} iterations ran${sel != null ? `; iteration ${String(sel).padStart(2, '0')} was selected as the final plan` : ''}.`);
  }

  // Benchmarks
  if (bench?.profit && ok(g.weeklyProfit)) {
    const p = bench.profit;
    add('benchmarks', 'Weekly profit by dataset', 'This run against 30 seeds', `${usd(g.weeklyProfit)} against a ${bench.n}-seed mean of ${usd(p.mean)} (range ${usd(p.min)} to ${usd(p.max)}).`);
  }

  // Scenarios
  if (ok(g.fuelCost) && n(g.fuelCost) > 0) {
    add('scenario_analysis', 'Baseline vs Scenario Economics', 'Fuel sensitivity', `Fuel costs ${usd(g.fuelCost)} a week, so every +10% on the bunker price takes ${usd(n(g.fuelCost) * 0.1)} off weekly profit.`);
  }
  if (ok(g.weeklyProfit) && total && n(g.weeklyProfit) > 0) {
    add('scenario_analysis', 'Weekly Net Profit', 'Headroom', `Profit reaches zero if every cost rises ${(n(g.weeklyProfit) / total * 100).toFixed(0)}%, or revenue falls ${ok(g.revenue) ? (n(g.weeklyProfit) / n(g.revenue) * 100).toFixed(0) : '—'}%.`);
  }
  return out;
}
