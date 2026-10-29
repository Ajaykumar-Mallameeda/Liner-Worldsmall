// Transshipment view (node --test): hubs, costs, connections from routed flows; reconciles with the engine ledger.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { transshipmentModel, hubAt } from '../src/utils/transshipment.js';
import { planKpis } from '../src/utils/runDiff.js';
import { reportModel } from '../src/utils/planReport.js';
import { tourFindings } from '../src/utils/tourFindings.js';

const TARIFFS = { H1: { transshipment_cost: 50, name: 'Hub one' }, H2: { transshipment_cost: 100 }, A: { transshipment_cost: 9 }, B: { transshipment_cost: 9 } };
const FLOWS = [
  { origin: 'A', destination: 'B', teu: 100, segments: [['s1', 'A', 'B']] },                                   // direct
  { origin: 'A', destination: 'C', teu: 40, segments: [['s1', 'A', 'H1'], ['s2', 'H1', 'C']] },               // one transfer
  { origin: 'D', destination: 'E', teu: 10, segments: [['s3', 'D', 'H1'], ['s2', 'H1', 'H2'], ['s4', 'H2', 'E']] }, // two
  { origin: 'X', destination: 'Y', teu: 0, segments: [['s1', 'X', 'H2'], ['s2', 'H2', 'Y']] },                 // empty: ignored
];

test('transshipmentModel: transfer ports, moves, per-hub cost and service connections', () => {
  const m = transshipmentModel({ flows: FLOWS, tariffs: TARIFFS, ledgerCost: 40 * 50 + 10 * 50 + 10 * 100 });
  assert.equal(m.totals.servedTeu, 150);
  assert.equal(m.totals.transferTeu, 50);
  assert.equal(m.totals.directTeu, 100);
  assert.equal(m.totals.moves, 60);                    // the two-transfer box counts twice
  assert.equal(m.totals.oneTransfer, 40);
  assert.equal(m.totals.twoPlus, 10);
  assert.equal(m.totals.flows, 2);
  assert.equal(m.totals.hubs, 2);
  assert.ok(Math.abs(m.totals.share - (50 / 150) * 100) < 1e-9);
  assert.equal(m.totals.cost, 3500);
  assert.equal(m.check.matches, true);
  const h1 = hubAt(m, 'H1');
  assert.equal(h1.teu, 50);
  assert.equal(h1.cost, 2500);
  assert.equal(h1.name, 'Hub one');
  assert.deepEqual(h1.pairs, [{ from: 's1', to: 's2', teu: 40 }, { from: 's3', to: 's2', teu: 10 }]);
  assert.deepEqual(h1.services, ['s1', 's2', 's3']);
  assert.equal(m.hubs[0].code, 'H1');                  // busiest first
  assert.equal(hubAt(m, 'A'), null);                   // origin handling is not transshipment
  assert.deepEqual(m.lanes[0], { o: 'A', d: 'C', teu: 40, via: ['H1'], services: ['s1', 's2'], cost: 2000 });
  assert.deepEqual(m.lanes[1].via, ['H1', 'H2']);
  assert.equal(m.lanes[1].cost, 1500);
});

test('transshipmentModel: without tariffs the TEU side stands and cost is unknown', () => {
  const m = transshipmentModel({ flows: FLOWS });
  assert.equal(m.totals.transferTeu, 50);
  assert.equal(m.totals.cost, null);
  assert.equal(hubAt(m, 'H1').cost, null);
  assert.equal(m.check.matches, null);
  assert.equal(transshipmentModel({}).totals.hubs, 0);
});

test('transshipmentModel: a mismatching ledger figure is reported, not hidden', () => {
  const m = transshipmentModel({ flows: FLOWS, tariffs: TARIFFS, ledgerCost: 9999 });
  assert.equal(m.check.matches, false);
});

// The recorded run and its dataset: the hub split must add up to the ledger's transshipment line exactly.
const RUN = new URL('../public/pipeline_output.json', import.meta.url);
const DATASET = new URL('../../data/datasets/worldsmall_json.json', import.meta.url);
test('recorded run: hubs reproduce the ledger cost and the engine\'s transshipped TEU', { skip: !(existsSync(RUN) && existsSync(DATASET)) }, () => {
  const raw = JSON.parse(readFileSync(RUN, 'utf8'));
  const led = raw.network_ledger;
  const ds = JSON.parse(readFileSync(DATASET, 'utf8'));
  const tariffs = Object.fromEntries(ds.ports.map((p) => [p.id, p]));
  const m = transshipmentModel({ flows: led.plan.flows, tariffs, ledgerCost: led.weekly_usd.transshipment_cost });
  assert.equal(m.check.matches, true, `computed ${m.totals.cost} vs ledger ${led.weekly_usd.transshipment_cost}`);
  const eng = led.strategy_report.extended_metrics.transshipment;
  assert.equal(m.totals.transferTeu, eng.teu);
  assert.equal(m.totals.moves, eng.transfer_moves_teu);
  assert.equal(m.totals.flows, eng.flows);
  assert.ok(Math.abs(m.totals.share - eng.share_of_served_teu_pct) < 1e-9);
  // (path_model's distinct_transfer_ports counts candidate paths; the hubs here are the ones cargo actually uses)
  assert.ok(m.totals.hubs > 0 && m.totals.hubs <= led.path_model.signals.transfer_concentration.distinct_transfer_ports);
  const sumHubs = m.hubs.reduce((a, h) => a + h.cost, 0);
  assert.ok(Math.abs(sumHubs - led.weekly_usd.transshipment_cost) < 1e-6);

  // The same figures reach Run diff, the PDF report and the guided tour.
  const k = planKpis({ services: raw.selected_services, ledger: led });
  assert.equal(k.transship_teu, eng.teu);
  assert.equal(k.transship_hubs, m.totals.hubs);
  const runtime = { raw, global: { selected_services: raw.selected_services, weeklyProfit: 1, revenue: 2 } };
  const rep = reportModel(runtime);
  const kpi = rep.kpis.find(([name]) => name === 'Transshipped');
  assert.ok(kpi, 'PDF report has the transshipment KPI');
  assert.equal(kpi[1], `${Math.round(eng.teu).toLocaleString('en-US')} TEU`);
  const tour = tourFindings(runtime).transshipment;
  assert.equal(tour.length, 1);
  assert.equal(tour[0].panel, 'Transfer hubs');
  assert.match(tour[0].text, new RegExp(`at ${m.totals.hubs} hubs`));
});
