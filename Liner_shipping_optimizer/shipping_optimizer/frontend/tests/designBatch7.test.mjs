// Batch 7 design ideas (node --test): D7 split-screen Run diff (diffSide, linked cameras).
import test from 'node:test';
import assert from 'node:assert/strict';
import { diffSide } from '../src/utils/runDiff.js';
import { joinSync, syncGroupSize } from '../src/services/mapSync.js';

const sv = (id, ports) => ({ id, ports, load: 10 });
const ROWS = [
  { status: 'kept', a: sv('s1', ['A', 'B']), b: sv('s9', ['A', 'B']) },
  { status: 'removed', a: sv('s2', ['C', 'D']), b: null },
  { status: 'added', a: null, b: sv('s3', ['E', 'F']) },
  { status: 'changed', a: sv('s4', ['A', 'G']), b: sv('s4', ['A', 'G', 'H']) },
];

test('diffSide: each map draws its own plan, statuses per side, both frame A ∪ B', () => {
  const a = diffSide(ROWS, 'A'); const b = diffSide(ROWS, 'B');
  assert.deepEqual(a.services.map((s) => s.id), ['A:s1', 'A:s2', 'A:s4']);
  assert.deepEqual(b.services.map((s) => s.id), ['B:s9', 'B:s3', 'B:s4']);
  assert.equal(a.status.get('A:s2'), 'removed');
  assert.equal(b.status.get('B:s3'), 'added');
  assert.equal(a.status.get('A:s4'), 'kept');
  assert.deepEqual(b.services[2].ports, ['A', 'G', 'H']);          // B's own version of a changed service
  assert.deepEqual(a.fitPorts, b.fitPorts);
  assert.deepEqual(a.fitPorts, ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']);
});

function fakeMap() {
  const h = {}; let cam = { center: { lng: 0, lat: 0 }, zoom: 1, bearing: 0, pitch: 0 }; const jumps = [];
  return {
    jumps,
    on: (t, f) => { h[t] = f; }, off: (t) => { delete h[t]; },
    getCenter: () => cam.center, getZoom: () => cam.zoom, getBearing: () => cam.bearing, getPitch: () => cam.pitch,
    jumpTo: (c) => { jumps.push(c); cam = { ...cam, ...c }; h.move?.({}); },
    move: (c) => { cam = { ...cam, ...c }; h.move?.({}); },
  };
}

test('mapSync: the map last touched leads, followers copy its camera and never echo', () => {
  const m1 = fakeMap(); const m2 = fakeMap();
  const el1 = new EventTarget(); const el2 = new EventTarget();
  const leave1 = joinSync('t', m1, el1); const leave2 = joinSync('t', m2, el2);
  assert.equal(syncGroupSize('t'), 2);
  m1.move({ zoom: 3 });                                  // nobody touched yet: no copy
  assert.equal(m2.jumps.length, 0);
  el1.dispatchEvent(new Event('pointerdown'));
  m1.move({ zoom: 4, center: { lng: 10, lat: 5 } });
  assert.equal(m2.jumps.length, 1);
  assert.equal(m2.jumps[0].zoom, 4);
  assert.equal(m1.jumps.length, 0);                      // m2's jump did not come back to m1
  el2.dispatchEvent(new Event('wheel'));
  m2.move({ zoom: 6 });
  assert.equal(m1.jumps.at(-1).zoom, 6);
  leave1(); leave2();
  assert.equal(syncGroupSize('t'), 0);
});

test('thumbZoom (D8): a port thumbnail covers about the asked ground, clamped to the mosaic zooms', async () => {
  const { thumbZoom, metresPerPixel } = await import('../src/utils/s2tiles.js');
  const z = thumbZoom(51.9, 88, 4000);                   // Rotterdam drawer card
  assert.equal(z, 11);                                    // 47 m per pixel: 4.1 km across
  const ground = metresPerPixel(51.9, z) * 88;
  assert.ok(ground > 4000 / 1.5 && ground < 4000 * 1.5, String(ground));
  assert.equal(thumbZoom(0, 40, 5000), 10);              // palette thumb at the equator: MIN_Z
  assert.equal(thumbZoom(60, 400, 100), 14);             // never past the native zoom
});

test('sheetAfterDrag (D9): up opens full, down steps back to half then closes, small drags stay', async () => {
  const { sheetAfterDrag } = await import('../src/utils/bottomSheet.js');
  assert.equal(sheetAfterDrag('half', -70), 'full');
  assert.equal(sheetAfterDrag('full', 90), 'half');
  assert.equal(sheetAfterDrag('half', 90), 'closed');
  assert.equal(sheetAfterDrag('half', 30), 'half');
});

test('paletteActions (D10): the three named commands and their variants become exact intents', async () => {
  const { parseActions, parseChange, RANGES } = await import('../src/utils/paletteActions.js');
  const one = (q) => { const a = parseActions(q); assert.equal(a.length, 1, `${q} → ${JSON.stringify(a)}`); return a[0]; };
  assert.deepEqual(one('close Suez').patch, { closure: 'suez' });
  assert.deepEqual(one('close the red sea').patch, { closure: 'red_sea' });
  assert.deepEqual(one('Close  Bosphorus').patch, { closure: 'bosporus' });
  assert.deepEqual(one('reopen suez').patch, { closure: null });
  assert.deepEqual(one('fuel +20%').patch, { fuelM: 1.2 });
  assert.deepEqual(one('fuel −30%').patch, { fuelM: 0.7 });
  assert.deepEqual(one('bunker price x1.5').patch, { fuelM: 1.5 });
  assert.equal(one('fuel +500%').patch.fuelM, RANGES.fuelM[1]);                 // clamped to the slider
  assert.deepEqual(one('demand -10%').patch, { demandM: 0.9 });
  assert.deepEqual(one('rates +30%').patch, { market: { rateM: 1.3, rateMode: 'uniform' } });
  assert.deepEqual(one('war risk on').patch, { market: { war: true } });
  assert.deepEqual(one('war-risk off').patch, { market: { war: false } });
  const d = one('compare with seed 7');
  assert.equal(d.kind, 'diff'); assert.equal(d.seed, 7);
  assert.equal(one('diff seed 12').seed, 12);
  assert.ok(parseActions('close s').length > 1);                                // ambiguous: several passages
  assert.deepEqual(parseActions('rotterdam'), []);
  assert.equal(parseChange('+20%'), 1.2); assert.equal(parseChange('20 %'), 1.2); assert.equal(parseChange('abc'), null);
});

test('tourFindings (D11): every sentence is computed from the run, panels named, missing numbers dropped', async () => {
  const { tourFindings } = await import('../src/utils/tourFindings.js');
  const runtime = {
    global: {
      weeklyProfit: 40e6, revenue: 100e6, totalCost: 60e6, fuelCost: 30e6, portCost: 20e6, transshipCost: 5e6,
      coverage: 50, weeklyDemand: 200000, lanes: 700, selected_iteration: 2,
      selected_services: [
        { id: 'a', weekly_profit: 5e6, ports: ['X', 'Y'], frequency_per_week: 1, vessel_class: 'Feeder_800', vessels: 3, leg_load_factor: 0.95 },
        { id: 'b', weekly_profit: -1e6, ports: ['X', 'Z'], frequency_per_week: 2, vessel_class: 'Panamax_2400', vessels: 5, leg_load_factor: 0.5 },
      ],
    },
    regions: { r1: { name: 'Asia', coverage: 60 }, r2: { name: 'Europe', coverage: 40 } },
    iterations: [{}, {}, {}],
  };
  const f = tourFindings(runtime, { n: 30, profit: { mean: 35e6, min: 20e6, max: 50e6 } });
  const text = (tab, panel) => f[tab].find((x) => x.panel === panel).text;
  assert.match(text('command_center', 'Current Decision'), /\$40\.0M profit on \$100\.0M revenue \(40\.0% margin\); above the 30-seed mean of \$35\.0M/);
  assert.match(text('command_center', 'Revenue to Profit'), /^Fuel: \$30\.0M a week, 50% of the \$60\.0M cost/);
  assert.match(text('network_intel', 'Selected Services'), /Most profitable: a, \$5\.0M a week\. 1 lose money \(−\$1\.0M together\)/);
  assert.match(text('network_intel', 'Network Canvas'), /^X is called by 2 of the 2 services/);
  assert.match(text('demand_intel', 'Coverage'), /50\.0% of 200,000 TEU a week is carried; 100,000 TEU/);
  assert.match(text('demand_intel', 'Regional Demand'), /Lowest coverage: Europe at 40\.0%; highest: Asia at 60\.0%/);
  assert.match(text('port_intel', 'Busiest Ports'), /^X \(3 calls a week\), Z \(2 calls a week\), Y \(1 calls a week\)/);
  assert.match(text('fleet_intel', 'Vessel Class Mix'), /ledger deploys 8 vessels \(round trip × weekly frequency\); Panamax_2400 is the largest class with 5 \(63%\)/);
  assert.match(text('fleet_intel', 'Leg Load Factor'), /Average leg load 73%; 1 of 2 services run 90% full/);
  assert.match(text('decision_center', 'Iteration Overview'), /3 iterations ran; iteration 02 was selected/);
  assert.match(text('scenario_analysis', 'Baseline vs Scenario Economics'), /every \+10% on the bunker price takes \$3\.0M/);
  assert.match(text('scenario_analysis', 'Weekly Net Profit'), /every cost rises 67%, or revenue falls 40%/);
  assert.deepEqual(tourFindings({ global: {} }), {});                    // nothing to say without a run
});

test('reportModel (D12): KPIs, a waterfall that adds up, and the service table fit one page', async () => {
  const { reportModel, TABLE_ROWS } = await import('../src/utils/planReport.js');
  const services = Array.from({ length: 40 }, (_, i) => ({ id: `s${i}`, weekly_profit: (20 - i) * 1e5, ports: ['A', 'B', `P${i % 5}`], frequency_per_week: 1, vessels: 2, vessel_class: 'Feeder_800', leg_load_factor: 0.5 }));
  const m = reportModel({ global: { weeklyProfit: 40e6, revenue: 100e6, operatingCost: 20e6, fuelCost: 30e6, portCost: 8e6, transshipCost: 2e6, coverage: 50, satisfiedDemand: 1e5, weeklyDemand: 2e5, selected_services: services } },
    { n: 30, profit: { mean: 38e6 }, coverage: { mean: 49 } });
  assert.equal(m.kpis.length, 6);
  assert.deepEqual(m.kpis[0], ['Weekly profit', '$40.00M', '+$2.00M vs 30-seed mean']);
  assert.equal(m.kpis[2][1], '40.0%');
  assert.equal(m.kpis[3][2], '+1.0 pp vs 30-seed mean');
  assert.equal(m.kpis[5][1], '40 · 80');
  assert.deepEqual(m.steps.map((s) => s.k), ['Revenue', 'Vessel operating', 'Fuel', 'Port', 'Transshipment', 'Profit']);
  assert.equal(m.steps.at(-2).to, 40e6);                                   // revenue minus the four lines lands on profit
  assert.equal(m.costCheck.costs, 60e6);
  assert.equal(m.rows.length, TABLE_ROWS);
  assert.equal(m.rows[0][0], 's0'); assert.equal(m.rows[0][6], '$2.00M');
  assert.match(m.tableNote, /Top 32 of 40 services/);
  assert.equal(m.rows.find((r) => r[0] === 's25')[6], '-$500K');
});
