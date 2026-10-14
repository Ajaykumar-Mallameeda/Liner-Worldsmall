// Consumer contract tests (node --test): missing / null / zero / valid metrics, leg load factor across departures,
// scenario baseline never fabricated.
import test from 'node:test';
import assert from 'node:assert/strict';
import { numOrNull, fmtOr, serviceLegLoadFactor, networkLegLoadFactor, fmtPct, sumOrNull, csvNumber, UNAVAILABLE } from '../src/utils/metrics.js';
import { extractBaselineState } from '../src/services/scenario/scenarioEngine.js';

test('missing, null, NaN, empty and boolean are unavailable; zero is a value', () => {
  for (const bad of [undefined, null, '', NaN, Infinity, true, 'abc']) assert.equal(numOrNull(bad), null);
  assert.equal(numOrNull(0), 0);
  assert.equal(numOrNull('0'), 0);
  assert.equal(numOrNull(-5.5), -5.5);
  assert.equal(fmtOr(null, (v) => `$${v}`), UNAVAILABLE);
  assert.equal(fmtOr(0, (v) => `$${v}`), '$0');
});

test('csv: missing profit is an empty cell, genuine zero is 0.00', () => {
  assert.equal(csvNumber(undefined), '');
  assert.equal(csvNumber(null), '');
  assert.equal(csvNumber(0), '0.00');
  assert.equal(csvNumber(12.345), '12.35');
});

test('sum: no numeric value is unavailable, zeros are summed', () => {
  assert.equal(sumOrNull([], (x) => x), null);
  assert.equal(sumOrNull([{ p: null }, {}], (x) => x.p), null);
  assert.equal(sumOrNull([{ p: 0 }, { p: 5 }], (x) => x.p), 5);
});

test('load greater than one departure capacity is valid across several departures (not >100 %)', () => {
  // weekly load 1324 TEU on a 900 TEU/departure service: ledger leg load factor 0.7356, never 147 %
  const s = { load: 1324, capacity: 900, leg_load_factor: 0.7355555555555555, carried_teu_legs: 3972, offered_teu_legs: 5400 };
  assert.ok(Math.abs(serviceLegLoadFactor(s) - 0.7356) < 1e-3);
  assert.equal(fmtPct(serviceLegLoadFactor(s)), '73.6%');
  // fallback from carried / offered when the factor is absent
  assert.equal(fmtPct(serviceLegLoadFactor({ carried_teu_legs: 3972, offered_teu_legs: 5400 })), '73.6%');
});

test('load factor without a backend basis is unavailable, not load / capacity and not 0', () => {
  assert.equal(serviceLegLoadFactor({ load: 1324, capacity: 900 }), null);
  assert.equal(fmtPct(serviceLegLoadFactor({ load: 0, capacity: 0 })), UNAVAILABLE);
  assert.equal(serviceLegLoadFactor({ leg_load_factor: 0 }), 0);          // a measured 0 is a value
  assert.equal(serviceLegLoadFactor(null), null);
});

test('network leg load factor is volume weighted and ignores services without data', () => {
  const f = networkLegLoadFactor([
    { carried_teu_legs: 100, offered_teu_legs: 200 },
    { carried_teu_legs: 300, offered_teu_legs: 400 },
    { load: 5 },                                         // no leg fields: excluded, not counted as 0 %
  ]);
  assert.equal(f, 400 / 600);
  assert.equal(networkLegLoadFactor([{ load: 1 }]), null);
  assert.equal(networkLegLoadFactor([]), null);
});

const good = () => ({
  summary_metrics: { weekly_profit: 26.6e6, revenue: 105e6, total_cost: 78.8e6, fuel_cost: 30.9e6, port_cost: 29e6,
    transship_cost: 1.3e6, operating_cost: 17.6e6, satisfied_demand: 93946, unserved_demand: 182548, coverage: 33.98, total_services: 31 },
  selected_services: [],
});

test('scenario baseline: valid output is read as is', () => {
  const b = extractBaselineState(good());
  assert.equal(b.weeklyProfit, 26.6e6);
  assert.equal(b.fuelCost, 30.9e6);
  assert.equal(b.coverage, 33.98);
  assert.equal(b.totalServices, 31);
});

test('scenario baseline: any missing figure makes the baseline unavailable, never a demo number', () => {
  for (const k of ['weekly_profit', 'fuel_cost', 'total_services', 'revenue', 'satisfied_demand', 'unserved_demand', 'port_cost']) {
    const j = good();
    delete j.summary_metrics[k];
    assert.equal(extractBaselineState(j), null, `missing ${k} must not be replaced`);
  }
  assert.equal(extractBaselineState(null), null);
  assert.equal(extractBaselineState({}), null);
});

test('scenario baseline: a genuine zero profit is kept (not replaced by a fallback)', () => {
  const j = good();
  j.summary_metrics.weekly_profit = 0;
  const b = extractBaselineState(j);
  assert.equal(b.weeklyProfit, 0);
});

test('scenario baseline: values from the independent ledger totals are used when summary fields are absent', () => {
  const j = good();
  j.summary_metrics = { satisfied_demand: 1, unserved_demand: 1, coverage: 50, total_services: 2 };
  j.network_ledger = { weekly_usd: { operating_profit: 5, revenue: 20, total_operating_cost: 15, fuel_cost: 3, port_call_fixed_cost: 2,
    port_variable_cost: 0, transshipment_cost: 1, vessel_cost: 4 } };
  const b = extractBaselineState(j);
  assert.equal(b.weeklyProfit, 5);
  assert.equal(b.portCost, 2);
});

test('scenario baseline: coverage is derived from satisfied / total demand when the field is absent (not a demo value)', () => {
  const j = good();
  delete j.summary_metrics.coverage;
  const b = extractBaselineState(j);
  assert.ok(Math.abs(b.coverage - (93946 / 276494) * 100) < 1e-9);
});
