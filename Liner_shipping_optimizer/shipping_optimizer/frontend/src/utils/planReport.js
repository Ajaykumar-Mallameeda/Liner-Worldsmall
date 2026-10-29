/**
 * planReport.js — what the one-page PDF plan report shows (design D12), as plain data so it can be tested:
 * the headline KPIs, the revenue → profit waterfall steps and the service table. services/planReportPdf.js draws it.
 * Every figure is read from the run on screen (runtime.global, the selected services) and the 30-seed baseline.
 */

import { ledgerForServices } from './portFlows.js';
import { transshipmentModel } from './transshipment.js';

export const TABLE_ROWS = 32;   // one page: two columns of 16 rows

const usd = (v) => {
  if (v == null || !Number.isFinite(Number(v))) return '-';
  const x = Number(v); const a = Math.abs(x);
  const s = a >= 1e9 ? `$${(a / 1e9).toFixed(2)}B` : a >= 1e6 ? `$${(a / 1e6).toFixed(2)}M` : a >= 1e3 ? `$${(a / 1e3).toFixed(0)}K` : `$${Math.round(a)}`;
  return x < 0 ? `-${s}` : s;
};
const num = (v) => (v == null || v === '' || !Number.isFinite(Number(v)) ? null : Number(v));
const int = (v) => (v == null ? '-' : Math.round(v).toLocaleString('en-US'));

export function reportModel(runtime, bench = null) {
  const g = runtime?.global || {};
  const services = (g.selected_services || []).filter((s) => s && s.id != null);
  const profit = num(g.weeklyProfit); const revenue = num(g.revenue);
  const vessels = services.reduce((a, s) => a + (num(s.vessels) || 0), 0);
  const vsMean = (v, st, f) => (v != null && st?.mean != null ? `${v - st.mean >= 0 ? '+' : '-'}${f(Math.abs(v - st.mean))} vs ${bench.n}-seed mean` : null);
  const kpis = [
    ['Weekly profit', usd(profit), vsMean(profit, bench?.profit, usd)],
    ['Revenue / week', usd(revenue), null],
    ['Margin', profit != null && revenue ? `${(profit / revenue * 100).toFixed(1)}%` : '-', 'profit / revenue'],
    ['Coverage', num(g.coverage) != null ? `${num(g.coverage).toFixed(1)}%` : '-', vsMean(num(g.coverage), bench?.coverage, (d) => `${d.toFixed(1)} pp`) || 'TEU served / demand'],
    ['TEU / week', num(g.satisfiedDemand) != null ? int(g.satisfiedDemand) : '-', num(g.weeklyDemand) != null ? `of ${int(g.weeklyDemand)} demand` : null],
    ['Services · vessels', `${services.length} · ${int(vessels)}`, `${new Set(services.flatMap((s) => s.ports || [])).size} ports called`],
  ];
  // Transshipment: cargo changing ship, from the plan's own ledger flows (none → the KPI is left out).
  const ledger = services.length ? ledgerForServices(runtime, services) : null;
  const tm = ledger ? transshipmentModel({ flows: ledger.plan.flows }) : null;
  if (tm) {
    kpis.push(['Transshipped', `${int(tm.totals.transferTeu)} TEU`,
      `${tm.totals.share.toFixed(1)}% · ${tm.totals.hubs} hubs${tm.hubs[0] ? ` · top ${tm.hubs.slice(0, 2).map((h) => h.code).join(', ')}` : ''}`]);
  }

  const lines = [['Vessel operating', g.operatingCost], ['Fuel', g.fuelCost], ['Port', g.portCost], ['Transshipment', g.transshipCost]]
    .map(([k, v]) => [k, num(v)]).filter(([, v]) => v != null);
  let steps = [];
  if (revenue != null && lines.length) {
    let run = revenue;
    steps = [{ k: 'Revenue', from: 0, to: revenue, kind: 'total' }];
    lines.forEach(([k, v]) => { steps.push({ k, from: run, to: run - v, kind: 'cost', v }); run -= v; });
    steps.push({ k: 'Profit', from: 0, to: profit ?? run, kind: 'total' });
  }

  const sorted = [...services].sort((a, b) => (num(b.weekly_profit) ?? -Infinity) - (num(a.weekly_profit) ?? -Infinity));
  const rows = sorted.slice(0, TABLE_ROWS).map((s) => [
    String(s.id), String(s.vessel_class || '-').replace(/_/g, ' '), `${num(s.frequency_per_week) ?? '-'}/wk`,
    String((s.ports || []).length), num(s.vessels) != null ? String(s.vessels) : '-',
    num(s.leg_load_factor) != null ? `${(num(s.leg_load_factor) * 100).toFixed(0)}%` : '-', usd(s.weekly_profit),
  ]);
  return {
    kpis, steps, rows, servicesTotal: services.length, transship: tm ? tm.totals : null,
    tableNote: services.length > TABLE_ROWS ? `Top ${TABLE_ROWS} of ${services.length} services by weekly profit.` : `All ${services.length} services, by weekly profit.`,
    costCheck: steps.length ? { costs: lines.reduce((a, [, v]) => a + v, 0), profit: steps[steps.length - 1].to } : null,
  };
}

export const SERVICE_COLUMNS = ['Service', 'Class', 'Freq', 'Calls', 'Vessels', 'Load', 'Profit / wk'];
