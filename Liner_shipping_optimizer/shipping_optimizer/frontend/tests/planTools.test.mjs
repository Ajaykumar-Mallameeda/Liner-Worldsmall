// Plan tools of the 2026-10-24 features (node --test): per-port activity and unserved demand, run diff
// matching, and the leg schedule the vessel animation and voyage timeline use.
import test from 'node:test';
import assert from 'node:assert/strict';
import { portActivity, ledgerForServices } from '../src/utils/portFlows.js';
import { rotationKey, diffPlans, diffOverlay, planKpis } from '../src/utils/runDiff.js';
import { legScheduleOf, positionAt } from '../src/utils/legTimes.js';

test('portActivity: served + unserved = demand per lane; totals reconcile; transshipment counted at the transfer port', () => {
  const flows = [
    { origin: 'A', destination: 'C', teu: 30, segments: [['s1', 'A', 'B'], ['s2', 'B', 'C']] },
    { origin: 'A', destination: 'B', teu: 50, segments: [['s1', 'A', 'B']] },
  ];
  const services = [{ id: 's1', ports: ['A', 'B'], frequency_per_week: 2 }, { id: 's2', ports: ['B', 'C'], frequency_per_week: 1 }];
  const demand = [['A', 'C', 100], ['A', 'B', 50], ['C', 'A', 20]];
  const act = portActivity({ flows, services, demand });
  assert.deepEqual(act.totals, { demand: 170, served: 80, unserved: 90 });
  assert.equal(act.totals.demand, act.totals.served + act.totals.unserved);
  const a = act.ports.get('A');
  assert.equal(a.exportTeu, 80);
  assert.equal(a.unservedOut, 70);
  assert.equal(a.unservedIn, 20);
  assert.equal(act.ports.get('B').transshipTeu, 30);
  assert.equal(act.ports.get('B').callsPerWeek, 3);
  assert.deepEqual(act.lanes.map((l) => [l.o, l.d, l.teu]), [['A', 'C', 70], ['C', 'A', 20]]);
});

test('portActivity: without demand the unserved side stays unknown, not zero-filled as served', () => {
  const act = portActivity({ flows: [{ origin: 'A', destination: 'B', teu: 5, segments: [] }], services: [], demand: null });
  assert.equal(act.hasDemand, false);
  assert.equal(act.lanes.length, 0);
  assert.equal(act.totals.served, 5);
});

test('ledgerForServices: picks the ledger of exactly the plan shown, else null', () => {
  const raw = {
    network_ledger: { plan: { services: [{ id: 'x' }, { id: 'y' }], flows: [{ teu: 1 }] } },
    iteration_results: [{ network_ledger: { plan: { services: [{ id: 'x' }], flows: [{ teu: 2 }] } } }],
  };
  assert.equal(ledgerForServices(raw, [{ id: 'y' }, { id: 'x' }]).plan.flows[0].teu, 1);
  assert.equal(ledgerForServices(raw, [{ id: 'x' }]).plan.flows[0].teu, 2);
  assert.equal(ledgerForServices(raw, [{ id: 'z' }]), null);
});

test('rotationKey: a loop listed from another port is the same rotation; direction matters', () => {
  assert.equal(rotationKey(['C', 'A', 'B']), rotationKey(['A', 'B', 'C']));
  assert.notEqual(rotationKey(['A', 'C', 'B']), rotationKey(['A', 'B', 'C']));
});

test('diffPlans: matches by rotation + class across new ids, then rotation only; the rest added / removed', () => {
  const a = { services: [
    { id: 'a1', ports: ['P', 'Q'], vessel_class: 'F', frequency_per_week: 1, weekly_profit: 10 },
    { id: 'a2', ports: ['Q', 'R', 'S'], vessel_class: 'F', frequency_per_week: 1, weekly_profit: 5 },
    { id: 'a3', ports: ['X', 'Y'], vessel_class: 'F', frequency_per_week: 1, weekly_profit: -2 },
    { id: 'a4', ports: ['M', 'N'], vessel_class: 'F', frequency_per_week: 1, weekly_profit: 1 },
  ] };
  const b = { services: [
    { id: 'b9', ports: ['Q', 'P'], vessel_class: 'F', frequency_per_week: 1, weekly_profit: 12 },
    { id: 'b8', ports: ['R', 'S', 'Q'], vessel_class: 'P', frequency_per_week: 1, weekly_profit: 7 },
    { id: 'b7', ports: ['Z', 'W'], vessel_class: 'F', frequency_per_week: 1, weekly_profit: 3 },
    { id: 'b6', ports: ['M', 'N'], vessel_class: 'F', frequency_per_week: 2, weekly_profit: 4 },
  ] };
  const { rows, counts } = diffPlans(a, b);
  assert.deepEqual(counts, { kept: 1, retimed: 1, changed: 1, removed: 1, added: 1 });
  const kept = rows.find((r) => r.status === 'kept');
  assert.equal(kept.a.id, 'a1'); assert.equal(kept.b.id, 'b9'); assert.equal(kept.dProfit, 2);
  assert.equal(rows.find((r) => r.status === 'removed').dProfit, 2);   // dropping a loss-maker: +2
  const ov = diffOverlay(rows);
  assert.equal(ov.services.length, 5);
  assert.equal(ov.status.get('A:a3'), 'removed');
  assert.equal(ov.status.get('B:b7'), 'added');
  assert.equal(ov.status.get('B:b8'), 'kept');
});

test('planKpis: ledger money and coverage, vessels from fleet_by_class', () => {
  const k = planKpis({ services: [{ frequency_per_week: 2 }, { frequency_per_week: 1 }], ledger: {
    weekly_usd: { operating_profit: 5, revenue: 20, total_operating_cost: 15, profit_margin_on_revenue: 0.25 },
    demand_teu_per_week: { coverage_pct: 40, served: 100 }, fleet_by_class: { F: { used: 3 }, P: { used: 2 } } } });
  assert.equal(k.profit, 5); assert.equal(k.margin_pct, 25); assert.equal(k.coverage_pct, 40);
  assert.equal(k.vessels, 5); assert.equal(k.departures, 3); assert.equal(k.services, 2);
});

test('legScheduleOf: run legs give sail + one stay per call; slack is cycle minus that', () => {
  const svc = { ports: ['A', 'B'], cycle_time_days: 16, port_stay_days: 1,
    legs: [{ from: 'A', to: 'B', distance_nm: 2908, sail_days: 6.73, load_teu: 10 }, { from: 'B', to: 'A', distance_nm: 2908, sail_days: 6.73, load_teu: 5 }] };
  const s = legScheduleOf(svc);
  assert.equal(s.source, 'run');
  assert.ok(Math.abs(s.activeDays - 15.46) < 1e-9);
  assert.ok(Math.abs(s.slackDays - 0.54) < 1e-9);
  // waiting at the first port, then sailing leg 0, then in port at B
  assert.equal(positionAt(s, 0.2).waiting, true);
  const mid = positionAt(s, 0.54 + 3.365);
  assert.equal(mid.leg, 0); assert.ok(Math.abs(mid.frac - 0.5) < 1e-9);
  assert.equal(positionAt(s, 0.54 + 6.73 + 0.5).atPort, 'B');
  assert.equal(positionAt(s, 16 + 0.2).waiting, true);   // wraps every cycle
});

test('legScheduleOf: older runs are estimated (cycle minus a day per call, split by distance)', () => {
  const coords = { A: [0, 0], B: [10, 0], C: [30, 0] };
  const s = legScheduleOf({ ports: ['A', 'B', 'C'], cycle_time_days: 9 }, (p) => coords[p]);
  assert.equal(s.source, 'estimated');
  const sea = s.legs.reduce((t, l) => t + l.sailDays, 0);
  assert.ok(Math.abs(sea - 6) < 1e-9);
  assert.ok(s.legs[1].sailDays > s.legs[0].sailDays);
  assert.equal(legScheduleOf({ ports: ['A'], cycle_time_days: 7 }), null);
});
