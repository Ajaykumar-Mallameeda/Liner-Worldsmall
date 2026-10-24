/**
 * benchStats.js — summary statistics for the frozen 30-seed benchmark, shared by the Benchmarks tab
 * and the "vs 30-seed mean" deltas on headline figures.
 */

// Two-sided 97.5% Student t quantiles, df 1..30; 1.96 beyond.
const T975 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131,
  2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042];

export const num = (v) => (v == null || Number.isNaN(Number(v)) ? null : Number(v));

/** Mean, median, sd, range and the 95% confidence interval of the mean. */
export function stats(values) {
  const v = values.filter((x) => x != null);
  const n = v.length;
  if (!n) return null;
  const mean = v.reduce((a, b) => a + b, 0) / n;
  const sorted = [...v].sort((a, b) => a - b);
  const median = n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
  const sd = n > 1 ? Math.sqrt(v.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1)) : 0;
  const t = n > 1 ? (T975[n - 2] ?? 1.96) : 0;
  const half = n > 1 ? (t * sd) / Math.sqrt(n) : 0;
  return { n, mean, median, sd, min: sorted[0], max: sorted[n - 1], lo: mean - half, hi: mean + half, cv: mean ? (sd / Math.abs(mean)) * 100 : null };
}

export function niceTicks(min, max, count = 4) {
  if (min === max) return [min];
  const span = max - min;
  const step0 = span / count;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) || 10 * mag;
  const out = [];
  for (let x = Math.ceil(min / step) * step; x <= max + 1e-9; x += step) out.push(x);
  return out;
}

/** A seed that failed (exit code ≠ 0) or whose ledger did not verify; left out of means and CIs. */
export const flagged = (r) => r.exit_code !== 0 || r.ledger_verified === false;

/** Benchmark dataset key for a dataset name as runs report it ("WorldSmall", "World-500", "baltic" ...). */
export function benchKeyFor(name, keys = ['baltic', 'WAF', 'worldsmall', 'world500', 'world1000']) {
  const n = String(name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  return keys.find((k) => k.toLowerCase().replace(/[^a-z0-9]/g, '') === n) || null;
}

/** Points ({ cov, profit }) that no other point beats on both coverage and profit, by ascending coverage. */
export function paretoFront(points) {
  const sorted = [...points].sort((a, b) => b.cov - a.cov || b.profit - a.profit);
  const out = []; let best = -Infinity;
  sorted.forEach((p) => { if (p.profit > best) { out.push(p); best = p.profit; } });
  return out.sort((a, b) => a.cov - b.cov);
}
