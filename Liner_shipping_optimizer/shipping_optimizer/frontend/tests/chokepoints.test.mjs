// Chokepoint helpers of the 2026-10-28 campaign (#2 / #4): PortWatch year-on-year change, detour passages, map points.
import test from 'node:test';
import assert from 'node:assert/strict';
import { yoyPct, addedPassages, CHOKEPOINT_AT } from '../src/services/chokepoints.js';
import { passageName } from '../src/services/seaRoutes.js';

test('yoyPct: change against a year earlier, null when either side is missing or zero', () => {
  assert.equal(yoyPct(3.4, 90.2).toFixed(1), '-96.2');
  assert.equal(yoyPct(110, 100), 10);
  assert.equal(yoyPct(null, 10), null);
  assert.equal(yoyPct(5, 0), null);
});

test('addedPassages: only what the detour adds', () => {
  assert.deepEqual(addedPassages({ via_before: ['suez', 'babalmandab', 'malacca'], via_after: ['gibraltar', 'south_africa', 'malacca'] }),
    ['gibraltar', 'south_africa']);
  assert.deepEqual(addedPassages({ via_before: ['malacca'], via_after: ['malacca'] }), []);
  assert.deepEqual(addedPassages({}), []);
});

test('CHOKEPOINT_AT: every point is a readable passage on the globe', () => {
  for (const [id, c] of Object.entries(CHOKEPOINT_AT)) {
    assert.ok(c.name && passageName(id), id);
    assert.ok(Math.abs(c.at[0]) <= 180 && Math.abs(c.at[1]) <= 90, id);
  }
  assert.ok(CHOKEPOINT_AT.babalmandab && CHOKEPOINT_AT.suez && CHOKEPOINT_AT.south_africa);
});
