/**
 * BenchSections — the detail sections of the Benchmarks tab, all from the per-seed records of the frozen
 * 30-seed benchmark (backend/run_catalog.py → /api/benchmark/<dataset>/seeds, or the static bundle):
 *
 *   DatasetCards       one card per dataset: problem size and the headline means
 *   CostStructure      share of each weekly cost line, dataset × line (one-hue heat table)
 *   StageTime          where the pipeline time goes, median seconds per stage (share bars)
 *   FleetDeployment    assigned / owned vessels per class (one-hue heat table)
 *   TransitQuality     transit p50–p90 range with direct vs transshipped means (two-series dot plot)
 *   SolverReliability  termination, gap to the LP bound, assertions, LLM fallback, reproducibility
 *   SeedExplorer       every seed of one dataset, sortable; a row opens that run
 *
 * Datasets differ ~400× in size, so every section compares shares, ratios or per-dataset scales, never one
 * absolute axis across datasets. Failed seeds (exit ≠ 0 or ledger not verified) are left out of means and
 * medians, as on the strip plots. Colours: --viz-1 (series / magnitude shading), --viz-2 (second series);
 * text stays in text tokens. Each chart has a table view (ChartFrame) or is itself a table.
 */

import React, { useMemo, useState } from 'react';
import { ChartFrame, useWidth } from './PlanCharts.jsx';
import { fmtUsd } from '../../utils/formatters.js';
import { num, stats, flagged } from '../../utils/benchStats.js';

const EM = '—';
const ok = (rows) => rows.filter((r) => !flagged(r));
const meanOf = (rows, k) => stats(ok(rows).map((r) => num(r[k])))?.mean ?? null;
const medianOf = (rows, k) => stats(ok(rows).map((r) => num(r[k])))?.median ?? null;
const pct = (v, d = 1) => (v == null ? EM : `${Number(v).toFixed(d)}%`);
const secs = (v) => (v == null ? EM : v >= 120 ? `${(v / 60).toFixed(1)} min` : `${Number(v).toFixed(1)} s`);
const fmtInt = (v) => (v == null ? EM : Math.round(v).toLocaleString('en-US'));
const Sw = ({ c, shape = 'bar' }) => <span className={`viz-sw viz-sw--${shape}`} style={{ background: shape === 'ring' ? 'transparent' : c, borderColor: c }} aria-hidden="true" />;

/** Cell shading for a share in [0, 1] of the row's maximum: one hue, light → strong. */
const shade = (k) => ({ background: `rgba(57, 135, 229, ${(0.06 + 0.5 * Math.max(0, Math.min(1, k))).toFixed(3)})` });

/* ── Dataset cards ───────────────────────────────────────────────────────── */

export function DatasetCards({ datasets }) {
  return (
    <div className="bm-cards">
      {datasets.map(({ k, label, list }) => {
        const good = ok(list);
        const any = list[0] || {};
        return (
          <div key={k} className="bm-card">
            <div className="bm-card-head">
              <b>{label}</b>
              <span>{any.ports != null ? `${any.ports} ports · ${fmtInt(any.od_records)} lanes` : EM}</span>
            </div>
            <div className="bm-card-v">{fmtUsd(meanOf(list, 'weekly_profit_usd'))}<small>/wk mean profit</small></div>
            <dl className="bm-card-dl">
              <div><dt>Coverage</dt><dd>{pct(meanOf(list, 'coverage_pct'))}</dd></div>
              <div><dt>Margin</dt><dd>{pct((meanOf(list, 'profit_margin_on_revenue') ?? 0) * 100)}</dd></div>
              <div><dt>Services</dt><dd>{fmtInt(meanOf(list, 'services_operated'))}</dd></div>
              <div><dt>Vessels</dt><dd>{fmtInt(meanOf(list, 'vessels_assigned'))}<span className="bm-dim"> / {fmtInt(any.vessels_owned)}</span></dd></div>
              <div><dt>Demand</dt><dd>{any.demand_total_teu != null ? `${(any.demand_total_teu / 1000).toFixed(0)}k TEU` : EM}</dd></div>
              <div><dt>Run time</dt><dd>{secs(medianOf(list, 'pipeline_sec'))}</dd></div>
            </dl>
            <div className={`bm-card-foot ${good.length < list.length ? 'warn' : ''}`}>
              {good.length}/{list.length} seeds OK{good.length < list.length ? ' ⚠' : ''}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Cost structure ──────────────────────────────────────────────────────── */

const COST_LINES = [
  ['cost_fuel_usd', 'Fuel'], ['cost_handling_usd', 'Handling'], ['cost_vessel_usd', 'Vessels'],
  ['cost_port_call_usd', 'Port calls'], ['cost_transshipment_usd', 'Transship'],
];

export function CostStructure({ datasets }) {
  const rows = datasets.map(({ k, label, list }) => {
    const total = meanOf(list, 'weekly_total_cost_usd');
    const vals = COST_LINES.map(([key]) => meanOf(list, key));
    const shares = vals.map((v) => (v != null && total ? v / total : null));
    return { k, label, total, vals, shares, rev: meanOf(list, 'weekly_revenue_usd') };
  });
  const top = rows.map((r) => r.shares.reduce((b, v, i) => (v != null && (b < 0 || v > r.shares[b]) ? i : b), -1));
  return (
    <div className="bm-heat-wrap">
      <table className="bm-heat" aria-label="Share of weekly cost by line and dataset">
        <thead>
          <tr><th scope="col">Dataset</th>{COST_LINES.map(([, l]) => <th key={l} scope="col" className="r">{l}</th>)}<th scope="col" className="r">Cost / wk</th></tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={r.k}>
              <th scope="row">{r.label}</th>
              {r.shares.map((s, i) => (
                <td key={i} className={`r ${i === top[ri] ? 'is-top' : ''}`} style={s != null ? shade(s / 0.45) : undefined}
                  title={`${r.label} · ${COST_LINES[i][1]}: ${fmtUsd(r.vals[i])}/wk (${pct(s != null ? s * 100 : null)} of cost)`}>
                  {pct(s != null ? s * 100 : null)}
                </td>
              ))}
              <td className="r" title={`Cost is ${pct(r.total && r.rev ? (r.total / r.rev) * 100 : null)} of revenue`}>{fmtUsd(r.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="viz-note">Mean over successful seeds; darker = larger share of that dataset's weekly cost, the largest line is outlined. Port variable cost is zero in every dataset and is left out.</div>
    </div>
  );
}

/* ── Where the time goes ─────────────────────────────────────────────────── */

const STAGES = [
  ['t_model_and_paths_sec', 'Model + paths'], ['t_milp_sec', 'MILP'], ['t_local_search_sec', 'Local search'],
  ['t_flow_reopt_sec', 'Flow re-opt'],
];

export function StageTime({ datasets }) {
  const rows = datasets.map(({ k, label, list }) => {
    const total = medianOf(list, 'pipeline_sec');
    const parts = STAGES.map(([key]) => medianOf(list, key));
    const known = parts.reduce((a, v) => a + (v || 0), 0);
    const outside = total != null ? Math.max(0, total - known) : null;
    return { k, label, total, parts, outside, llm: medianOf(list, 't_llm_latency_sec'), plan: medianOf(list, 'optimiser_plan_sec') };
  });
  const csv = {
    columns: [['dataset', (r) => r.label], ...STAGES.map(([, l], i) => [`${l} (median s)`, (r) => r.parts[i]]), ['agents, LLM and checks (s)', (r) => r.outside], ['pipeline median (s)', (r) => r.total]],
    rows,
  };
  return (
    <ChartFrame
      exportName="benchmark_stage_time" exportTitle="Median pipeline time by stage" csv={csv}
      legend={(<><span><Sw c="var(--viz-1)" />MILP</span><span><Sw c="var(--viz-muted)" />Other planner stages</span><span><Sw c="var(--viz-track)" />Agents, LLM calls and checks</span></>)}
      note="Bars are shares of each dataset's median pipeline time (own 100%); the label is the median total. LLM latency is part of the agents segment."
      table={(
        <table className="viz-table"><thead><tr><th>Dataset</th>{STAGES.map(([, l]) => <th key={l}>{l}</th>)}<th>Agents / LLM / checks</th><th>Total</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.k}><td>{r.label}</td>{r.parts.map((v, i) => <td key={i}>{secs(v)}</td>)}<td>{secs(r.outside)}</td><td>{secs(r.total)}</td></tr>)}</tbody>
        </table>
      )}
    >
      {({ show, hide }) => (
        <div className="bm-share-rows">
          {rows.map((r) => {
            const segs = [...r.parts.map((v, i) => ({ v, label: STAGES[i][1], hero: i === 1 })), { v: r.outside, label: 'Agents, LLM calls and checks', rest: true }];
            return (
              <div key={r.k} className="bm-share-row">
                <span className="bm-share-name">{r.label}</span>
                <div className="bm-share-bar" role="img" aria-label={`${r.label}: median ${secs(r.total)}; MILP ${secs(r.parts[1])}`}>
                  {segs.map((s, i) => (s.v && r.total ? (
                    <span key={i} className={`bm-seg ${s.hero ? 'is-hero' : s.rest ? 'is-rest' : ''}`} style={{ flexGrow: s.v / r.total }}
                      onMouseMove={(e) => show(e, [`${r.label} · ${s.label}`, `${secs(s.v)} (median)`, `${pct((s.v / r.total) * 100)} of the run`, s.rest && r.llm != null ? `LLM latency ${secs(r.llm)}` : null].filter(Boolean))}
                      onMouseLeave={hide} />
                  ) : null))}
                </div>
                <span className="bm-share-total">{secs(r.total)}</span>
              </div>
            );
          })}
        </div>
      )}
    </ChartFrame>
  );
}

/* ── Fleet deployment ────────────────────────────────────────────────────── */

/** "Panamax_2400" -> "Pmx 2400", "Post_panamax" -> "Post-Pmx", "Feeder_450" -> "Fdr 450". */
const shortClass = (c) => c.replace(/^Feeder_/, 'Fdr ').replace(/^Panamax_/, 'Pmx ').replace(/^Post_panamax$/, 'Post-Pmx').replace(/^Super_panamax$/, 'Super-Pmx').replace(/_/g, ' ');

export function FleetDeployment({ datasets }) {
  const classes = useMemo(() => {
    const seen = [];
    datasets.forEach(({ list }) => list.forEach((r) => Object.keys(r.fleet_by_class || {}).forEach((c) => { if (!seen.includes(c)) seen.push(c); })));
    const cap = (c) => Number((c.match(/(\d+)/) || [0, c.includes('Super') ? 9000 : c.includes('Post') ? 8000 : 0])[1]);
    return seen.sort((a, b) => cap(a) - cap(b));
  }, [datasets]);
  const cell = (list, c) => {
    const rs = ok(list).map((r) => r.fleet_by_class?.[c]).filter(Boolean);
    if (!rs.length) return null;
    const owned = rs[0].owned;
    const assigned = rs.reduce((a, x) => a + (x.assigned || 0), 0) / rs.length;
    return { owned, assigned, share: owned ? assigned / owned : null };
  };
  return (
    <div className="bm-heat-wrap">
      <table className="bm-heat" aria-label="Vessels assigned of vessels owned, by class and dataset">
        <thead><tr><th scope="col">Dataset</th>{classes.map((c) => <th key={c} scope="col" className="r" title={c.replace(/_/g, ' ')}>{shortClass(c)}</th>)}<th scope="col" className="r">All</th></tr></thead>
        <tbody>
          {datasets.map(({ k, label, list }) => (
            <tr key={k}>
              <th scope="row">{label}</th>
              {classes.map((c) => {
                const x = cell(list, c);
                return (
                  <td key={c} className="r" style={x?.share != null ? shade(x.share) : undefined}
                    title={x ? `${label} · ${c}: ${x.assigned.toFixed(1)} of ${x.owned} vessels sailing on average` : `${label} has no ${c}`}>
                    {x ? <>{pct(x.share != null ? x.share * 100 : null, 0)}<div className="bm-dim bm-sub">{x.assigned.toFixed(0)}/{x.owned}</div></> : EM}
                  </td>
                );
              })}
              <td className="r">{pct((meanOf(list, 'deployment_ratio') ?? null) != null ? meanOf(list, 'deployment_ratio') * 100 : null, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="viz-note">Share of each class's owned vessels that the plan sails (mean over successful seeds, assigned/owned beside it). Darker = more of the class in use; a full class (100%) limits the plan.</div>
    </div>
  );
}

/* ── Transit quality ─────────────────────────────────────────────────────── */

export function TransitQuality({ datasets }) {
  const [ref, W] = useWidth();
  const rows = datasets.map(({ k, label, list }) => ({
    k, label,
    p50: meanOf(list, 'transit_days_p50'), p90: meanOf(list, 'transit_days_p90'), mean: meanOf(list, 'transit_days_mean'),
    direct: meanOf(list, 'transit_days_direct'), trans: meanOf(list, 'transit_days_transshipped'),
    share: meanOf(list, 'transship_share_pct'),
    feeder: meanOf(list, 'transship_feeder_teu'), hub: meanOf(list, 'transship_hub_and_spoke_teu'), multi: meanOf(list, 'transship_multi_hop_teu'),
  }));
  const hi = Math.max(10, ...rows.flatMap((r) => [r.p90, r.trans, r.direct].filter((v) => v != null)));
  const xMax = Math.ceil(hi / 10) * 10;
  const L = 96, R = 112, rowH = 34, T = 8, H = T + rows.length * rowH + 26;
  const x = (v) => L + (W - L - R) * (v / xMax);
  const ticks = Array.from({ length: xMax / 10 + 1 }, (_, i) => i * 10);
  const csv = { columns: [['dataset', (r) => r.label], ['transit p50 (d)', (r) => r.p50], ['transit p90 (d)', (r) => r.p90], ['mean direct (d)', (r) => r.direct], ['mean transshipped (d)', (r) => r.trans], ['transshipped share %', (r) => r.share]], rows };
  return (
    <ChartFrame
      exportName="benchmark_transit" exportTitle="Transit time by dataset" csv={csv}
      legend={(<><span><Sw c="var(--viz-muted)" />p50 – p90 range</span><span><Sw c="var(--viz-1)" shape="dot" />Direct cargo, mean</span><span><Sw c="var(--viz-2)" shape="ring" />Transshipped cargo, mean</span></>)}
      note="TEU-weighted transit days of the routed cargo (sailing + port stays + transfer dwell), averaged over successful seeds. Right: share of served TEU that changes service at least once."
      table={(
        <table className="viz-table"><thead><tr><th>Dataset</th><th>p50</th><th>p90</th><th>Direct</th><th>Transshipped</th><th>Transshipped TEU</th><th>Feeder / hub / multi-hop TEU</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.k}><td>{r.label}</td><td>{r.p50?.toFixed(1)} d</td><td>{r.p90?.toFixed(1)} d</td><td>{r.direct?.toFixed(1)} d</td><td>{r.trans?.toFixed(1)} d</td><td>{pct(r.share)}</td><td>{fmtInt(r.feeder)} / {fmtInt(r.hub)} / {fmtInt(r.multi)}</td></tr>)}</tbody>
        </table>
      )}
    >
      {({ show, hide }) => (
        <div ref={ref}>
          <svg width={W} height={H} role="img" aria-label="Transit time range and direct versus transshipped means by dataset">
            {ticks.map((t) => (
              <g key={t}>
                <line x1={x(t)} x2={x(t)} y1={T} y2={H - 22} className="viz-grid" />
                <text x={x(t)} y={H - 6} className="viz-axis" textAnchor="middle">{t} d</text>
              </g>
            ))}
            {rows.map((r, i) => {
              const cy = T + i * rowH + rowH / 2;
              const tip = [r.label, `p50 ${r.p50?.toFixed(1)} d · p90 ${r.p90?.toFixed(1)} d`, `direct ${r.direct?.toFixed(1)} d · transshipped ${r.trans?.toFixed(1)} d`, `${pct(r.share)} of served TEU transshipped`];
              return (
                <g key={r.k} onMouseMove={(e) => show(e, tip)} onMouseLeave={hide}>
                  <rect x={0} y={cy - rowH / 2} width={W} height={rowH} fill="transparent" />
                  <text x={L - 10} y={cy + 4} className="viz-axis bm-rowlabel" textAnchor="end">{r.label}</text>
                  {r.p50 != null && r.p90 != null && <rect x={x(r.p50)} y={cy - 6} width={Math.max(2, x(r.p90) - x(r.p50))} height={12} rx={4} className="bm-range" />}
                  {r.direct != null && <circle cx={x(r.direct)} cy={cy} r={5} className="viz-dot is-front" />}
                  {r.trans != null && <circle cx={x(r.trans)} cy={cy} r={5} className="viz-ring" />}
                  <text x={W - R + 12} y={cy + 4} className="viz-val">{pct(r.share)} trans.</text>
                </g>
              );
            })}
          </svg>
        </div>
      )}
    </ChartFrame>
  );
}

/* ── Solver and reliability ──────────────────────────────────────────────── */

// src/network/solve_semantics.py conclusions, in words
const TERMINATION = {
  optimal_for_restricted_service_set: 'optimal on restricted set',
  feasible_time_limit_gap_unresolved: 'time limit, gap open',
};
const termLabel = (t) => TERMINATION[t] || String(t || 'unknown').replace(/_/g, ' ');

export function SolverReliability({ datasets }) {
  return (
    <div className="bm-heat-wrap">
      <table className="bm-table bm-table--compact bm-table--fit" aria-label="Solver outcome and run reliability by dataset">
        <thead>
          <tr>
            <th scope="col">Dataset</th><th scope="col">MILP outcome (runs)</th><th scope="col" className="r">Gap to bound</th>
            <th scope="col" className="r">MILP</th><th scope="col" className="r">Assertions</th><th scope="col">LLM fallback</th>
          </tr>
        </thead>
        <tbody>
          {datasets.map(({ k, label, list, repro }) => {
            const good = ok(list);
            const terms = {};
            list.forEach((r) => { const t = r.termination || 'unknown'; terms[t] = (terms[t] || 0) + 1; });
            const proven = list.filter((r) => r.proven_optimal).length;
            const g = stats(good.map((r) => num(r.gap_to_bound_pct)));
            const passed = list.reduce((a, r) => a + (r.assertions_passed || 0), 0);
            const failed = list.reduce((a, r) => a + (r.assertions_failed || 0), 0);
            const fails = [...new Set(list.flatMap((r) => r.failed_assertions || []))];
            const fallback = list.reduce((a, r) => a + (r.llm_fallback_uses || 0), 0);
            const r429 = list.reduce((a, r) => a + (r.llm_http_429 || 0), 0);
            return (
              <tr key={k}>
                <th scope="row">{label}</th>
                <td title={`${proven} of ${list.length} runs proven optimal over the full model; peak memory ${fmtInt(medianOf(list, 'peak_mb_python'))} MB (median)`}>
                  {Object.entries(terms).sort((a, b) => b[1] - a[1]).map(([t, n]) => (
                    <div key={t}>{termLabel(t)}<span className="bm-dim"> {n}</span></div>
                  ))}
                </td>
                <td className="r">{g ? `${g.median.toFixed(1)}%` : EM}<div className="bm-dim">{g ? `${g.min.toFixed(1)}–${g.max.toFixed(1)}` : ''}</div></td>
                <td className="r">{secs(medianOf(list, 't_milp_sec'))}</td>
                <td className={`r ${failed ? 'warn' : ''}`} title={fails.length ? `Failed: ${fails.join('; ')}` : 'All assertions passed'}>
                  {passed + failed ? `${((passed / (passed + failed)) * 100).toFixed(2)}%` : EM}{failed ? <div>{failed} failed ⚠</div> : null}
                </td>
                <td title={`${fallback} fallback uses, ${r429} HTTP 429 responses over ${list.length} runs`}>
                  {fallback}<span className="bm-dim"> · {r429}× 429</span>
                  {repro?.seeds_compared ? <div className="bm-dim">{repro.identical_profit_to_1_cent}/{repro.seeds_compared} reproduced</div> : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="viz-note">Gap to bound: median (range) distance between the plan and the LP relaxation bound of the capped MILP; it bounds how far the plan can be from that model's optimum. No run is proven optimal over the full model. "Reproduced" = seeds whose profit matched the reference run to the cent.</div>
    </div>
  );
}

/* ── Seed explorer ───────────────────────────────────────────────────────── */

const SEED_COLS = [
  ['seed', 'Seed', (v) => String(v).padStart(2, '0')],
  ['weekly_profit_usd', 'Profit / wk', fmtUsd],
  ['coverage_pct', 'Coverage', (v) => pct(v)],
  ['profit_margin_on_revenue', 'Margin', (v) => pct(v != null ? v * 100 : null)],
  ['services_operated', 'Services', fmtInt],
  ['vessels_assigned', 'Vessels', fmtInt],
  ['teu_utilisation_avg', 'Load factor', (v) => pct(v != null ? v * 100 : null)],
  ['transit_days_mean', 'Transit', (v) => (v == null ? EM : `${v.toFixed(1)} d`)],
  ['gap_to_bound_pct', 'Gap', (v) => pct(v)],
  ['pipeline_sec', 'Run time', secs],
  ['llm_regime', 'LLM', (v) => (v ? v.replace(/_/g, ' ') : EM)],
];

export function SeedExplorer({ label, list, onOpen, dsKey }) {
  const [sort, setSort] = useState({ k: 'weekly_profit_usd', dir: -1 });
  const rows = useMemo(() => [...list].sort((a, b) => {
    const va = a[sort.k]; const vb = b[sort.k];
    if (va == null) return 1;
    if (vb == null) return -1;
    return (va > vb ? 1 : va < vb ? -1 : 0) * sort.dir;
  }), [list, sort]);
  const best = Math.max(...ok(list).map((r) => r.weekly_profit_usd ?? -Infinity));
  return (
    <div className="bm-heat-wrap bm-seed-wrap">
      <table className="bm-table bm-table--compact" aria-label={`${label}: every seed`}>
        <thead>
          <tr>
            {SEED_COLS.map(([k, l]) => (
              <th key={k} scope="col" className={k === 'seed' || k === 'llm_regime' ? '' : 'r'} aria-sort={sort.k === k ? (sort.dir > 0 ? 'ascending' : 'descending') : 'none'}>
                <button type="button" className="bm-sort" onClick={() => setSort((s) => ({ k, dir: s.k === k ? -s.dir : -1 }))}>
                  {l}{sort.k === k ? (sort.dir > 0 ? ' ▲' : ' ▼') : ''}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.seed} className={`bm-seed-row ${flagged(r) ? 'is-flagged' : ''}`} tabIndex={0}
              onClick={() => onOpen(dsKey, r.seed)} onKeyDown={(e) => { if (e.key === 'Enter') onOpen(dsKey, r.seed); }}
              title={`Open ${label} seed ${String(r.seed).padStart(2, '0')} in every tab`}>
              {SEED_COLS.map(([k, , f]) => (
                <td key={k} className={k === 'seed' || k === 'llm_regime' ? '' : 'r'}>
                  {f(r[k])}{k === 'seed' && flagged(r) ? ' ⚠' : ''}{k === 'weekly_profit_usd' && r.weekly_profit_usd === best ? ' ★' : ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="viz-note">Click a header to sort; Enter or click on a row opens that seed in every tab. ★ best profit · ⚠ failed run (left out of means).</div>
    </div>
  );
}
