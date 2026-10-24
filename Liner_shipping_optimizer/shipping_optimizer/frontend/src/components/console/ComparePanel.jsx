/**
 * ComparePanel — two iterations of the run side by side, each against the frozen 30-seed benchmark mean
 * of the same dataset, plus which services one iteration has that the other does not.
 * Opened from the Current Decision panel's Compare button or the command palette.
 */

import React, { useMemo, useState } from 'react';
import { fmtNum, fmtPct, fmtUsd } from '../../utils/formatters.js';
import { downloadCsv } from '../../utils/exportData.js';

const EM = '—';
const pad2 = (n) => String(n).padStart(2, '0');

const ROWS = [
  { k: 'profit', label: 'Weekly profit', f: fmtUsd, d: (v) => fmtUsd(v), bench: 'profit' },
  { k: 'coverage', label: 'Demand coverage', f: (v) => fmtPct(v), d: (v) => `${v.toFixed(1)} pp`, bench: 'coverage' },
  { k: 'servicesDeployed', label: 'Services', f: (v) => fmtNum(v), fb: (v) => v.toFixed(1), d: (v) => fmtNum(v), bench: 'services' },
  { k: 'marginPct', label: 'Margin on revenue', f: (v) => fmtPct(v), d: (v) => `${v.toFixed(1)} pp`, bench: 'marginPct' },
  { k: 'satisfiedDemand', label: 'TEU served / wk', f: (v) => fmtNum(Math.round(v)), d: (v) => fmtNum(Math.round(v)), bench: 'served' },
  { k: 'unservedDemand', label: 'TEU unserved / wk', f: (v) => fmtNum(Math.round(v)), d: (v) => fmtNum(Math.round(v)), bench: 'unserved', lowerIsBetter: true },
  { k: 'score', label: 'Convergence score', f: (v) => v.toFixed(3), d: (v) => v.toFixed(3) },
];

export default function ComparePanel({ iterations = [], iterResults = [], selectedIter, bench, runLabel, onClose }) {
  const others = iterations.filter((i) => i.iter !== selectedIter);
  const [a, setA] = useState(selectedIter ?? iterations[0]?.iter ?? null);
  const [b, setB] = useState(() => {
    const best = [...others].sort((x, y) => (y.profit ?? -Infinity) - (x.profit ?? -Infinity))[0];
    return best?.iter ?? iterations[iterations.length - 1]?.iter ?? null;
  });
  const A = iterations.find((i) => i.iter === a) || {};
  const B = iterations.find((i) => i.iter === b) || {};

  const diff = useMemo(() => {
    const sv = (n) => (iterResults.find((r) => (r.iteration ?? null) === n)?.selected_services) || [];
    const sa = sv(a); const sb = sv(b);
    const ia = new Set(sa.map((s) => String(s.id))); const ib = new Set(sb.map((s) => String(s.id)));
    return {
      onlyB: sb.filter((s) => !ia.has(String(s.id))),
      onlyA: sa.filter((s) => !ib.has(String(s.id))),
      both: sa.filter((s) => ib.has(String(s.id))).length,
      known: sa.length > 0 && sb.length > 0,
    };
  }, [iterResults, a, b]);

  const pick = (value, set, label) => (
    <select aria-label={label} value={value ?? ''} onChange={(e) => set(Number(e.target.value))} className="cmp-select">
      {iterations.map((i) => <option key={i.iter} value={i.iter}>iter {pad2(i.iter)}{i.iter === selectedIter ? ' (selected)' : ''}</option>)}
    </select>
  );

  const sum = (list) => list.reduce((t, s) => t + Number(s.weekly_profit || 0), 0);

  return (
    <div className="cmp">
      <div className="cmp-head">
        <span>Compare</span>{pick(a, setA, 'First iteration')}<span>with</span>{pick(b, setB, 'Second iteration')}
        <span className="cmp-sp" />
        <button type="button" className="cmp-btn" onClick={() => downloadCsv(`${runLabel || 'run'}_compare_iter${a}_iter${b}`,
          [['metric', (r) => r.label], [`iter_${a}`, (r) => A[r.k]], [`iter_${b}`, (r) => B[r.k]], ['difference', (r) => (A[r.k] != null && B[r.k] != null ? B[r.k] - A[r.k] : null)],
            ['seed_mean', (r) => (r.bench && bench?.[r.bench] ? bench[r.bench].mean : null)], ['seed_ci_lo', (r) => (r.bench && bench?.[r.bench] ? bench[r.bench].lo : null)], ['seed_ci_hi', (r) => (r.bench && bench?.[r.bench] ? bench[r.bench].hi : null)]], ROWS)}>CSV</button>
        <button type="button" className="cmp-btn" onClick={onClose}>Close</button>
      </div>
      <div className="cmp-table-wrap">
        <table className="viz-table cmp-table">
          <thead>
            <tr>
              <th>Metric</th><th>iter {a != null ? pad2(a) : EM}</th><th>iter {b != null ? pad2(b) : EM}</th><th>Difference</th>
              <th title="Frozen benchmark of this dataset; failed / unverified seeds left out">{bench ? `${bench.n}-seed mean (95% CI)` : 'Seed mean'}</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r) => {
              const va = A[r.k]; const vb = B[r.k];
              const d = va != null && vb != null ? vb - va : null;
              const better = d == null || Math.abs(d) < 1e-9 ? 0 : (d > 0) !== Boolean(r.lowerIsBetter) ? 1 : -1;
              const st = r.bench && bench ? bench[r.bench] : null;
              return (
                <tr key={r.k}>
                  <td>{r.label}</td>
                  <td>{va != null ? r.f(va) : EM}</td>
                  <td>{vb != null ? r.f(vb) : EM}</td>
                  <td className={better > 0 ? 'cmp-up' : better < 0 ? 'cmp-down' : ''}>
                    {d == null ? EM : better === 0 ? 'same' : `${better > 0 ? '▲' : '▼'} ${d > 0 ? '+' : '−'}${r.d(Math.abs(d))}`}
                  </td>
                  <td>{st ? `${(r.fb || r.f)(st.mean)} (${(r.fb || r.f)(st.lo)} – ${(r.fb || r.f)(st.hi)})` : EM}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="cmp-diff">
        {!diff.known ? (
          <span className="viz-note">The run file does not list services per iteration, so the service difference is not available.</span>
        ) : (
          <>
            <div>
              <div className="cmp-diff-h">Only in iter {pad2(b)} · {diff.onlyB.length} · {fmtUsd(sum(diff.onlyB))}/wk</div>
              <div className="cmp-ids">{diff.onlyB.length ? diff.onlyB.map((s) => <span key={s.id} title={`${fmtUsd(s.weekly_profit)}/wk · ${(s.ports || []).join(' → ')}`}>{s.id}</span>) : <span className="none">none</span>}</div>
            </div>
            <div>
              <div className="cmp-diff-h">Only in iter {pad2(a)} · {diff.onlyA.length} · {fmtUsd(sum(diff.onlyA))}/wk</div>
              <div className="cmp-ids">{diff.onlyA.length ? diff.onlyA.map((s) => <span key={s.id} title={`${fmtUsd(s.weekly_profit)}/wk · ${(s.ports || []).join(' → ')}`}>{s.id}</span>) : <span className="none">none</span>}</div>
            </div>
            <div className="viz-note">{diff.both} services are in both iterations.</div>
          </>
        )}
      </div>
    </div>
  );
}
