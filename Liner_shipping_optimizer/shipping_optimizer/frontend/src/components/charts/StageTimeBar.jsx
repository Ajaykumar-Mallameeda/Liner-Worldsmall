/**
 * StageTimeBar — where the network planner's time went, one stacked bar per plan:
 * model & paths → MILP → local search → flow re-optimisation → repair → ledger
 * (network_ledger.reconciliation.stage_timing; per iteration under iteration_results[i]).
 *
 * The MILP segment carries the series colour (it is the story: most of the run); the other stages are muted
 * steps with 2 px gaps and direct labels where they fit. A tick marks the MILP time budget. Hover any segment
 * for its seconds and share; the table view lists them all. The bar grows in only when the timings change.
 */
import React, { useMemo } from 'react';
import { ChartFrame, useWidth, growOf } from './PlanCharts.jsx';

const STAGES = [
  { k: 'model_and_paths_sec', label: 'Model & paths', short: 'Model' },
  { k: 'milp_sec', label: 'MILP solve', short: 'MILP', hero: true },
  { k: 'local_search_sec', label: 'Local search', short: 'LS' },
  { k: 'flow_reopt_sec', label: 'Flow re-optimisation', short: 'Flow' },
  { k: 'repair_sec', label: 'Profit repair', short: 'Repair' },
  { k: 'ledger_sec', label: 'Ledger', short: 'Ledger' },
];
const MUTED = ['var(--viz-muted)', 'var(--viz-muted-2)'];
const sec = (v) => (v >= 10 ? `${v.toFixed(1)} s` : v >= 0.1 ? `${v.toFixed(2)} s` : v > 0 ? `${(v * 1000).toFixed(0)} ms` : '0 s');

/** stage_timing of an iteration's plan, else of the run's final plan. */
export function stageTimingOf(raw, iter) {
  const ledgerTiming = (l) => l?.reconciliation?.stage_timing || l?.optimality?.stage_timing || null;
  const r = (raw?.iteration_results || []).find((x) => (x.iteration ?? null) === iter);
  return ledgerTiming(r?.network_ledger) || ledgerTiming(raw?.network_ledger);
}

export default function StageTimeBar({ timing, label = 'plan', exportBase = 'run', compact = false }) {
  const [ref, W] = useWidth();
  const rows = useMemo(() => {
    if (!timing) return [];
    const out = STAGES.filter((s) => timing[s.k] != null).map((s) => ({ ...s, v: Math.max(0, Number(timing[s.k])) }));
    const total = Number(timing.plan_total_sec) || out.reduce((a, r) => a + r.v, 0);
    const rest = total - out.reduce((a, r) => a + r.v, 0);
    if (rest > 0.05) out.push({ k: 'other', label: 'Other (not timed separately)', short: 'Other', v: rest });
    return out.map((r) => ({ ...r, share: total ? (r.v / total) * 100 : 0, total }));
  }, [timing]);
  if (!rows.length) return <div className="cx-compact-empty">This run file has no planner stage timings.</div>;

  const total = rows[0].total;
  const milp = rows.find((r) => r.hero);
  const budget = Number(timing.milp_budget_sec) || null;
  const H = compact ? 34 : 52, BAR = compact ? 14 : 18, L = 0, R = 0, T = compact ? 4 : 18;
  const x = (v) => L + (W - L - R) * (v / (total || 1));
  let acc = 0; let muted = 0;
  const segs = rows.map((r) => {
    const s = { ...r, x0: x(acc), x1: x(acc + r.v), fill: r.hero ? 'var(--viz-1)' : MUTED[muted++ % 2] };
    acc += r.v;
    return s;
  });
  const milpStart = segs.find((s) => s.hero)?.x0 ?? 0;
  const grow = growOf(`stage|${label}|${rows.map((r) => r.v.toFixed(3)).join('|')}`);   // grows in again only when the timings change

  return (
    <ChartFrame
      exportName={`${exportBase}_planner_stage_time`}
      exportTitle={`Planner time by stage (${label})`}
      csv={{ columns: [['stage', (r) => r.label], ['seconds', (r) => r.v], ['share_pct', (r) => r.share]], rows }}
      legend={<><span><span className="viz-sw" style={{ background: 'var(--viz-1)' }} aria-hidden="true" />MILP solve</span><span><span className="viz-sw" style={{ background: 'var(--viz-muted)' }} aria-hidden="true" />Other stages</span>{budget && <span><span className="viz-sw viz-sw--tick" style={{ background: 'var(--viz-ink)' }} aria-hidden="true" />MILP budget {sec(budget)}</span>}</>}
      note={milp ? `MILP took ${sec(milp.v)} of ${sec(total)} (${milp.share.toFixed(0)}%) for the ${label}.${budget ? ` Its time budget was ${sec(budget)}.` : ''}` : `${sec(total)} in total for the ${label}.`}
      table={(
        <table className="viz-table"><thead><tr><th>Stage</th><th>Time</th><th>Share</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.k}><td>{r.label}</td><td>{sec(r.v)}</td><td>{r.share.toFixed(1)}%</td></tr>)}
            <tr><td><b>Total</b></td><td><b>{sec(total)}</b></td><td>100%</td></tr></tbody>
        </table>
      )}
    >
      {({ show, hide }) => (
        <div ref={ref}>
          <svg width={W} height={H} role="img" aria-label={`Planner time by stage: ${rows.map((r) => `${r.label} ${sec(r.v)}`).join(', ')}`}>
            <g key={grow.key} className={grow.cls} style={{ transformOrigin: '0 0' }}>
              {segs.map((s) => {
                const w = Math.max(1, s.x1 - s.x0 - 2);   // 2 px surface gap between segments
                const fits = w > (s.hero ? 120 : 64);
                return (
                  <g key={s.k} onMouseMove={(e) => show(e, [s.label, sec(s.v), `${s.share.toFixed(1)}% of ${sec(total)}`])} onMouseLeave={hide}>
                    <rect x={s.x0} y={T} width={w} height={BAR} rx={3} fill={s.fill} />
                    <rect x={s.x0} y={0} width={Math.max(w, 6)} height={H} fill="transparent" />
                    {fits && !compact && <text x={s.x0 + 6} y={T + BAR + 14} className="viz-axis">{s.label} · {sec(s.v)}</text>}
                  </g>
                );
              })}
            </g>
            {budget && milp && <line x1={milpStart + x(budget)} x2={milpStart + x(budget)} y1={T - 3} y2={T + BAR + 3} className="viz-target" />}
            {!compact && <text x={W} y={12} className="viz-val" textAnchor="end">{sec(total)} total</text>}
          </svg>
        </div>
      )}
    </ChartFrame>
  );
}
