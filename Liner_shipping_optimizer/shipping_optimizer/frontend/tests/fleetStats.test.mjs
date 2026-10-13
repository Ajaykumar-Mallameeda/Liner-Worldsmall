// Consumer test (node --test): utilisation is a leg load factor, never weekly cargo / per-departure capacity;
// unknown stays unknown (null), never 0; vessels are summed from the plan, not counted as services.
import test from 'node:test';
import assert from 'node:assert/strict';
import { computeFleetStats } from '../src/utils/fleetStats.js';

const svc = (o) => ({ vessel_class: 'Panamax_2400', region: 'Asia', load: 0, capacity: 4800, vessels: 1, ...o });

test('weekly cargo above per-departure capacity is not reported as >100 % utilisation', () => {
  // 2 legs x 4800 offered, 5258 TEU-legs carried -> 54.8 %, not 109.5 %
  const s = computeFleetStats([svc({ load: 5258, offered_teu_legs: 9600, carried_teu_legs: 5258 })]);
  assert.equal(s.legLoadFactorPct, 54.8);
  assert.equal(s.utilizationPct, 54.8);
});

test('missing leg data is unknown, not zero', () => {
  const s = computeFleetStats([svc({ load: 5258 })]);
  assert.equal(s.legLoadFactorPct, null);
  assert.equal(s.utilizationPct, null);
});

test('vessels are the sum of assigned vessels, not the number of services', () => {
  const s = computeFleetStats([svc({ vessels: 9, offered_teu_legs: 1, carried_teu_legs: 1 }),
                               svc({ vessels: 4, offered_teu_legs: 1, carried_teu_legs: 1 })]);
  assert.equal(s.totalVessels, 13);
  assert.equal(s.serviceCount, 2);
});

test('aggregation is volume weighted (sum carried / sum offered)', () => {
  const s = computeFleetStats([svc({ offered_teu_legs: 1000, carried_teu_legs: 1000 }),
                               svc({ offered_teu_legs: 3000, carried_teu_legs: 0 })]);
  assert.equal(s.legLoadFactorPct, 25.0);
});
