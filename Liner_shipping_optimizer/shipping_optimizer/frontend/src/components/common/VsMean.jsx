/**
 * VsMean — one line under a headline figure: its difference from the frozen 30-seed benchmark mean
 * of the same dataset. Direction is shown by an arrow and a word, never by colour alone; the tooltip
 * carries the mean, its 95% CI, the seed spread and how many seeds were used.
 */

import React from 'react';
import { fmtUsd, fmtNum } from '../../utils/formatters.js';

const fmtBy = {
  usd: (v) => fmtUsd(v),
  pct: (v) => `${v.toFixed(1)}%`,
  pp: (v) => `${v.toFixed(1)} pp`,
  count: (v) => fmtNum(Math.round(v * 10) / 10),
};

export default function VsMean({ value, stat, unit = 'usd', n, excluded = 0, label = 'seed mean' }) {
  if (value == null || !stat) return <span className="cd-vs is-na" title="No benchmark for this dataset">vs bench —</span>;
  const delta = Number(value) - stat.mean;
  const show = unit === 'pct' ? 'pp' : unit;
  const tol = Math.max(Math.abs(stat.mean) * 0.005, unit === 'count' ? 0.5 : 0);
  const dir = Math.abs(delta) <= tol ? 0 : delta > 0 ? 1 : -1;
  const z = stat.sd ? delta / stat.sd : null;
  const f = fmtBy[unit];
  const title = [
    `${n}-${label}: ${f(stat.mean)} (95% CI ${f(stat.lo)} – ${f(stat.hi)})`,
    `seed range ${f(stat.min)} – ${f(stat.max)}, sd ${fmtBy[show](stat.sd)}`,
    excluded ? `${excluded} failed or unverified seed${excluded > 1 ? 's' : ''} left out` : null,
    z != null ? `this figure is ${Math.abs(z).toFixed(1)} sd ${delta >= 0 ? 'above' : 'below'} the mean` : null,
  ].filter(Boolean).join('\n');
  const sign = delta > 0 ? '+' : delta < 0 ? '−' : '±';
  return (
    <span className={`cd-vs ${dir > 0 ? 'is-up' : dir < 0 ? 'is-down' : 'is-flat'}`} title={title}>
      <span aria-hidden="true">{dir > 0 ? '▲' : dir < 0 ? '▼' : '='}</span>
      {dir === 0 ? ` at ${n}-${label}` : ` ${sign}${fmtBy[show](Math.abs(delta))} vs ${n}-${label}`}
    </span>
  );
}
