// Benchmark yardstick (node --test): summary statistics, failed-seed exclusion, dataset-key mapping,
// Pareto front of profit vs coverage, and agent-label matching for the cross-filter.
import test from 'node:test';
import assert from 'node:assert/strict';
import { stats, flagged, benchKeyFor, paretoFront, niceTicks } from '../src/utils/benchStats.js';
import { agentKey, sameAgent, matchesAgent } from '../src/services/focusStore.js';

test('stats: mean, sample sd and a t-based 95% CI; missing values ignored', () => {
  const s = stats([1, 2, 3, 4, null]);
  assert.equal(s.n, 4);
  assert.equal(s.mean, 2.5);
  assert.equal(s.median, 2.5);
  assert.ok(Math.abs(s.sd - 1.2909944) < 1e-6);
  // t(0.975, df 3) = 3.182
  assert.ok(Math.abs((s.hi - s.mean) - (3.182 * s.sd) / 2) < 1e-9);
  assert.equal(stats([]), null);
  assert.equal(stats([7]).sd, 0);
});

test('flagged: non-zero exit or unverified ledger is left out; missing flag is not', () => {
  assert.equal(flagged({ exit_code: 1, ledger_verified: true }), true);
  assert.equal(flagged({ exit_code: 0, ledger_verified: false }), true);
  assert.equal(flagged({ exit_code: 0 }), false);
});

test('benchKeyFor maps run dataset names to benchmark keys', () => {
  assert.equal(benchKeyFor('WorldSmall'), 'worldsmall');
  assert.equal(benchKeyFor('World-500'), 'world500');
  assert.equal(benchKeyFor('world1000'), 'world1000');
  assert.equal(benchKeyFor('waf'), 'WAF');
  assert.equal(benchKeyFor('Baltic'), 'baltic');
  assert.equal(benchKeyFor('Mars'), null);
  assert.equal(benchKeyFor(null), null);
});

test('paretoFront keeps only undominated points, by ascending coverage', () => {
  const pts = [
    { id: 'a', cov: 40, profit: 10 },
    { id: 'b', cov: 50, profit: 8 },
    { id: 'c', cov: 45, profit: 9 },
    { id: 'd', cov: 42, profit: 7 },   // beaten by c
    { id: 'e', cov: 50, profit: 6 },   // beaten by b (same coverage, less profit)
  ];
  assert.deepEqual(paretoFront(pts).map((p) => p.id), ['a', 'c', 'b']);
  assert.deepEqual(paretoFront([]), []);
  // one point that beats all others is the whole front
  assert.deepEqual(paretoFront([{ cov: 1, profit: 1 }, { cov: 2, profit: 2 }]).map((p) => p.cov), [2]);
});

test('niceTicks covers the range with round steps', () => {
  const t = niceTicks(0, 132.8e6, 4);
  assert.equal(t[0], 0);
  assert.ok(t[t.length - 1] <= 132.8e6 && t.length >= 3);
});

test('agent labels match regardless of case, spaces or underscores', () => {
  assert.equal(agentKey('Middle East'), 'middle_east');
  assert.ok(sameAgent('middle_east', 'Middle East'));
  assert.ok(!sameAgent('Asia', null));
  assert.ok(matchesAgent({ agent_region: 'Asia', region: 'Asia Pacific' }, 'asia'));
  assert.ok(!matchesAgent({ agent_region: 'Europe', region: 'Asia Pacific' }, 'Asia'));
  assert.ok(matchesAgent({ region: 'Europe' }, null));
});
