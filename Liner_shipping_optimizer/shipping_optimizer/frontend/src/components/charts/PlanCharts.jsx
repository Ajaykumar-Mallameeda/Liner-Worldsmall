/**
 * PlanCharts — four read-outs of the plan on screen, all from the run file (and, for the scatter, the
 * frozen 30-seed benchmark of the same dataset):
 *   CostWaterfall      revenue → each weekly cost line → profit
 *   ProfitCoverage     profit vs coverage of the benchmark seeds, their Pareto front, this run's iterations
 *   ServicePnl         weekly profit of every selected service, diverging around zero
 *   AgentCoverage      demand coverage of each regional agent against the 70% target; click = cross-filter
 *
 * Colours are the validated pair (--viz-1 series, --viz-2 flag); text stays in text tokens. Every chart has
 * a hover tooltip and a table view (ChartFrame).
 */

import React, { useEffect, useRef, useState } from 'react';
import { fmtUsd, fmtNum, fmtPct } from '../../utils/formatters.js';
import { niceTicks, paretoFront } from '../../utils/benchStats.js';
import { downloadCsv, downloadSvgPng } from '../../utils/exportData.js';
import { matchesAgent, sameAgent, toggleAgentFocus, useAgentFocus } from '../../services/focusStore.js';

const EM = '—';
const usdAxis = (v) => (Math.abs(v) >= 1e6 ? `$${(v / 1e6).toFixed(Math.abs(v) >= 1e7 ? 0 : 1)}M` : Math.abs(v) >= 1e3 ? `$${(v / 1e3).toFixed(0)}K` : `$${v}`);

// Callback ref: the plot unmounts while the table view is shown, so re-observe whenever it remounts.
function useWidth(fallback = 480) {
  const [el, setEl] = useState(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(([e]) => setW(Math.max(240, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, [el]);
  return [setEl, w];
}

/** Chart / table switch, PNG / CSV export, legend row, and one tooltip shared by the marks. */
export function ChartFrame({ legend, table, note, csv, exportName = 'chart', exportTitle = '', children }) {
  const [mode, setMode] = useState('chart');
  const [tip, setTip] = useState(null);
  const wrap = useRef(null);
  const show = (e, lines) => {
    const r = wrap.current?.getBoundingClientRect();
    if (!r) return;
    setTip({ x: e.clientX - r.left, y: e.clientY - r.top, w: r.width, lines });
  };
  const hide = () => setTip(null);
  return (
    <div className="viz-frame">
      <div className="viz-bar">
        <div className="viz-legend">{legend}</div>
        <div className="viz-actions">
          <div className="viz-toggle" role="group" aria-label="View">
            <button type="button" aria-pressed={mode === 'chart'} onClick={() => setMode('chart')}>Chart</button>
            <button type="button" aria-pressed={mode === 'table'} onClick={() => setMode('table')}>Table</button>
          </div>
          <div className="viz-toggle" role="group" aria-label="Export">
            <button type="button" disabled={mode !== 'chart'} title="Save the chart as a PNG image"
              onClick={() => downloadSvgPng(wrap.current?.querySelector('svg'), exportName, { title: exportTitle })}>PNG</button>
            {csv && <button type="button" title="Save the table as CSV" onClick={() => downloadCsv(exportName, csv.columns, csv.rows)}>CSV</button>}
          </div>
        </div>
      </div>
      {mode === 'chart' ? (
        <div className="viz-plot" ref={wrap} onMouseLeave={hide}>
          {children({ show, hide })}
          {tip && (
            <div className="viz-tip" style={{ left: Math.min(tip.x + 12, tip.w - 190), top: Math.max(tip.y - 10, 0) }} role="tooltip">
              {tip.lines.map((l, i) => <div key={i} className={i === 0 ? 'h' : ''}>{l}</div>)}
            </div>
          )}
        </div>
      ) : (
        <div className="viz-table-wrap">{table}</div>
      )}
      {note && <div className="viz-note">{note}</div>}
    </div>
  );
}

const Sw = ({ c, shape = 'bar' }) => <span className={`viz-sw viz-sw--${shape}`} style={{ background: shape === 'ring' ? 'transparent' : c, borderColor: c }} aria-hidden="true" />;

/* ── 1. Cost waterfall ───────────────────────────────────────────────────── */

export function CostWaterfall({ revenue, lines = [], profit, exportBase = 'run' }) {
  const [ref, W] = useWidth();
  if (revenue == null || !lines.length) return <div className="cx-compact-empty">This run has no revenue / cost breakdown.</div>;
  const steps = [{ k: 'Revenue', from: 0, to: revenue, kind: 'total' }];
  let run = revenue;
  lines.forEach(([k, v]) => { steps.push({ k, from: run, to: run - v, kind: 'cost', v }); run -= v; });
  const end = profit ?? run;
  steps.push({ k: 'Profit', from: 0, to: end, kind: 'total' });
  const H = 220, L = 52, R = 8, T = 18, B = 34;
  const lo = Math.min(0, ...steps.map((s) => Math.min(s.from, s.to)));
  const hi = Math.max(...steps.map((s) => Math.max(s.from, s.to)));
  const ticks = niceTicks(lo, hi, 4);
  const y0 = Math.min(lo, ticks[0]); const y1 = Math.max(hi, ticks[ticks.length - 1]);
  const y = (v) => T + (H - T - B) * (1 - (v - y0) / (y1 - y0 || 1));
  const band = (W - L - R) / steps.length;
  const bw = Math.min(56, band * 0.62);
  const cap = (s) => (s.k === 'Revenue' || s.k === 'Profit' ? s.k : s.k.charAt(0).toUpperCase() + s.k.slice(1));
  // Narrow panels (phone): short step names and whole-million values so neighbouring labels don't collide.
  const narrow = band < 72;
  const SHORT = { Revenue: 'Rev.', Operating: 'Oper.', Transshipment: 'Trans.', Profit: 'Profit', Fuel: 'Fuel', Port: 'Port' };
  const money = (v) => (narrow && Math.abs(v) >= 1e7 ? `${v < 0 ? '-' : ''}$${Math.round(Math.abs(v) / 1e6)}M` : fmtUsd(v));
  const share = (v) => (revenue ? `${((v / revenue) * 100).toFixed(1)}% of revenue` : '');
  return (
    <ChartFrame
      exportName={`${exportBase}_revenue_to_profit`}
      exportTitle="Weekly revenue to profit"
      csv={{ columns: [['step', (s) => cap(s)], ['usd_per_week', (s) => (s.kind === 'cost' ? -s.v : s.to)], ['share_of_revenue_pct', (s) => (revenue ? ((s.kind === 'cost' ? s.v : s.to) / revenue) * 100 : null)]], rows: steps }}
      legend={<><span><Sw c="var(--viz-1)" />Revenue, profit</span><span><Sw c="var(--viz-muted)" />Weekly cost line</span></>}
      note={`Weekly, selected plan. Costs sum to ${fmtUsd(revenue - end)}; revenue − costs = profit ${fmtUsd(end)}.`}
      table={(
        <table className="viz-table"><thead><tr><th>Step</th><th>$ / week</th><th>Share of revenue</th></tr></thead>
          <tbody>{steps.map((s) => <tr key={s.k}><td>{cap(s)}</td><td>{s.kind === 'cost' ? `−${fmtUsd(s.v)}` : fmtUsd(s.to)}</td><td>{share(s.kind === 'cost' ? s.v : s.to)}</td></tr>)}</tbody>
        </table>
      )}
    >
      {({ show, hide }) => (
        <div ref={ref}>
          <svg width={W} height={H} role="img" aria-label="Weekly revenue to profit waterfall">
            {ticks.map((t) => (
              <g key={t}>
                <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className={t === 0 ? 'viz-base' : 'viz-grid'} />
                <text x={L - 6} y={y(t) + 4} className="viz-axis" textAnchor="end">{usdAxis(t)}</text>
              </g>
            ))}
            {steps.map((s, i) => {
              const cx = L + band * i + band / 2;
              const top = y(Math.max(s.from, s.to)); const h = Math.max(1, Math.abs(y(s.from) - y(s.to)));
              const fill = s.kind === 'cost' ? 'var(--viz-muted)' : s.to < 0 ? 'var(--viz-2)' : 'var(--viz-1)';
              const val = s.kind === 'cost' ? `−${money(s.v)}` : money(s.to);
              const next = steps[i + 1];
              return (
                <g key={s.k}>
                  {next && <line x1={cx + bw / 2} x2={cx + band - bw / 2} y1={y(s.to)} y2={y(s.to)} className="viz-conn" />}
                  <rect x={cx - bw / 2} y={top} width={bw} height={h} rx={3} fill={fill} />
                  <rect x={cx - band / 2} y={T} width={band} height={H - T - B} fill="transparent"
                    onMouseMove={(e) => show(e, [cap(s), val, share(s.kind === 'cost' ? s.v : s.to)])} onMouseLeave={hide} />
                  <text x={cx} y={top - 5} className="viz-val" textAnchor="middle">{val}</text>
                  <text x={cx} y={H - B + 16} className="viz-axis" textAnchor="middle">{narrow ? (SHORT[cap(s)] || cap(s)) : cap(s)}</text>
                </g>
              );
            })}
          </svg>
        </div>
      )}
    </ChartFrame>
  );
}

/* ── 2. Profit vs coverage, Pareto front ─────────────────────────────────── */

export function ProfitCoverage({ seeds = [], iterations = [], selectedIter, currentSeed = null, dataset, exportBase = 'run' }) {
  const [ref, W] = useWidth();
  const S = seeds.filter((r) => r.coverage_pct != null && r.weekly_profit_usd != null)
    .map((r) => ({ cov: Number(r.coverage_pct), profit: Number(r.weekly_profit_usd), seed: r.seed }));
  const I = iterations.filter((it) => it.coverage != null && it.profit != null).map((it) => ({ cov: it.coverage, profit: it.profit, iter: it.iter }));
  if (!S.length && !I.length) return <div className="cx-compact-empty">No profit / coverage points for this dataset.</div>;
  const front = paretoFront(S);
  const onFront = new Set(front.map((p) => p.seed));
  const all = [...S, ...I];
  const H = 240, L = 52, R = 12, T = 12, B = 34;
  const xs = all.map((p) => p.cov); const ys = all.map((p) => p.profit);
  const padX = Math.max(0.5, (Math.max(...xs) - Math.min(...xs)) * 0.08); const padY = Math.max(1, (Math.max(...ys) - Math.min(...ys)) * 0.1);
  const xt = niceTicks(Math.min(...xs) - padX, Math.max(...xs) + padX, 5); const yt = niceTicks(Math.min(...ys) - padY, Math.max(...ys) + padY, 4);
  const x0 = Math.min(xt[0], Math.min(...xs) - padX); const x1 = Math.max(xt[xt.length - 1], Math.max(...xs) + padX);
  const y0 = Math.min(yt[0], Math.min(...ys) - padY); const y1 = Math.max(yt[yt.length - 1], Math.max(...ys) + padY);
  const x = (v) => L + (W - L - R) * ((v - x0) / (x1 - x0 || 1));
  const y = (v) => T + (H - T - B) * (1 - (v - y0) / (y1 - y0 || 1));
  const sel = I.find((p) => p.iter === selectedIter);
  return (
    <ChartFrame
      exportName={`${exportBase}_profit_vs_coverage`}
      exportTitle="Weekly profit vs demand coverage"
      csv={{ columns: [['point', (p) => (p.iter != null ? `iter ${p.iter}` : `seed ${p.seed}`)], ['coverage_pct', (p) => p.cov], ['weekly_profit_usd', (p) => p.profit], ['pareto_front', (p) => (p.seed != null ? onFront.has(p.seed) : '')]], rows: [...I, ...S] }}
      legend={(
        <>
          {S.length > 0 && <span><Sw c="var(--viz-1)" shape="dot" />Benchmark seed ({S.length})</span>}
          {front.length > 1 && <span><Sw c="var(--viz-1)" shape="line" />Pareto front</span>}
          {I.length > 0 && <span><Sw c="var(--viz-2)" shape="ring" />This run, by iteration</span>}
          {sel && <span><Sw c="var(--viz-2)" shape="dot" />Selected iteration</span>}
        </>
      )}
      note={S.length ? `${front.length} of ${S.length} ${dataset || ''} seeds are on the front: no other seed has both higher profit and higher coverage.` : 'No benchmark seeds for this dataset; iterations only.'}
      table={(
        <table className="viz-table"><thead><tr><th>Point</th><th>Coverage</th><th>$ / week</th><th>Pareto</th></tr></thead>
          <tbody>
            {I.map((p) => <tr key={`i${p.iter}`}><td>iter {p.iter}{p.iter === selectedIter ? ' (selected)' : ''}</td><td>{fmtPct(p.cov)}</td><td>{fmtUsd(p.profit)}</td><td>{EM}</td></tr>)}
            {[...S].sort((a, b) => b.profit - a.profit).map((p) => <tr key={`s${p.seed}`}><td>seed {p.seed}{p.seed === currentSeed ? ' (this run)' : ''}</td><td>{fmtPct(p.cov)}</td><td>{fmtUsd(p.profit)}</td><td>{onFront.has(p.seed) ? 'yes' : 'no'}</td></tr>)}
          </tbody>
        </table>
      )}
    >
      {({ show, hide }) => (
        <div ref={ref}>
          <svg width={W} height={H} role="img" aria-label="Weekly profit against demand coverage">
            {yt.map((t) => (
              <g key={`y${t}`}>
                <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="viz-grid" />
                <text x={L - 6} y={y(t) + 4} className="viz-axis" textAnchor="end">{usdAxis(t)}</text>
              </g>
            ))}
            {xt.map((t) => <text key={`x${t}`} x={x(t)} y={H - B + 16} className="viz-axis" textAnchor="middle">{`${+t.toFixed(2)}%`}</text>)}
            <text x={W - R} y={H - 4} className="viz-axis" textAnchor="end">demand coverage →</text>
            {front.length > 1 && <polyline points={front.map((p) => `${x(p.cov)},${y(p.profit)}`).join(' ')} className="viz-front" />}
            {S.map((p) => (
              <circle key={`s${p.seed}`} cx={x(p.cov)} cy={y(p.profit)} r={onFront.has(p.seed) ? 4.5 : 3.5}
                className={`viz-dot ${onFront.has(p.seed) ? 'is-front' : ''} ${p.seed === currentSeed ? 'is-current' : ''}`}
                onMouseMove={(e) => show(e, [`Seed ${p.seed}${p.seed === currentSeed ? ' (this run)' : ''}`, `${fmtUsd(p.profit)} / week`, `${fmtPct(p.cov)} coverage`, onFront.has(p.seed) ? 'On the Pareto front' : 'Dominated'])} onMouseLeave={hide} />
            ))}
            {I.map((p) => {
              const isSel = p.iter === selectedIter;
              return (
                <g key={`i${p.iter}`} onMouseMove={(e) => show(e, [`Iteration ${p.iter}${isSel ? ' (selected)' : ''}`, `${fmtUsd(p.profit)} / week`, `${fmtPct(p.cov)} coverage`])} onMouseLeave={hide}>
                  <circle cx={x(p.cov)} cy={y(p.profit)} r={isSel ? 6 : 5} className={isSel ? 'viz-sel' : 'viz-ring'} />
                </g>
              );
            })}
            {sel && <text x={x(sel.cov) + 9} y={y(sel.profit) - 8} className="viz-val">iter {sel.iter}</text>}
          </svg>
        </div>
      )}
    </ChartFrame>
  );
}

/* ── 3. Per-service P&L, diverging ───────────────────────────────────────── */

export function ServicePnl({ services = [], maxRows = 400, exportBase = 'run' }) {
  const [ref, W] = useWidth();
  const [focus] = useAgentFocus();
  const rows = services.filter((s) => s.weekly_profit != null && matchesAgent(s, focus))
    .map((s) => ({ id: String(s.id ?? EM), p: Number(s.weekly_profit), rev: s.revenue, cost: s.cost, agent: s.agent_region ?? s.region, ports: s.ports || [], margin: s.margin_pct }))
    .sort((a, b) => b.p - a.p).slice(0, maxRows);
  if (!rows.length) return <div className="cx-compact-empty">No per-service profit{focus ? ` for the ${focus} agent` : ''} in this run.</div>;
  const losers = rows.filter((r) => r.p < 0);
  const lo = Math.min(0, ...rows.map((r) => r.p)); const hi = Math.max(0, ...rows.map((r) => r.p));
  const ROW = 15, L = 118, R = 58, T = 18;
  const H = T + rows.length * ROW + 4;
  const x = (v) => L + (W - L - R) * ((v - lo) / (hi - lo || 1));
  const ticks = niceTicks(lo, hi, 3);
  const totalLoss = losers.reduce((a, r) => a + r.p, 0);
  return (
    <ChartFrame
      exportName={`${exportBase}_profit_by_service`}
      exportTitle={`Weekly profit by service${focus ? ` (${focus} agent)` : ''}`}
      csv={{ columns: [['service', (r) => r.id], ['agent', (r) => r.agent], ['weekly_profit_usd', (r) => r.p], ['revenue_usd', (r) => r.rev], ['cost_usd', (r) => r.cost], ['margin_pct', (r) => r.margin], ['port_calls', (r) => r.ports.length], ['ports', (r) => r.ports.join(' ')]], rows }}
      legend={<><span><Sw c="var(--viz-1)" />Profit</span><span><Sw c="var(--viz-2)" />Loss</span>{focus && <span className="viz-chip">agent: {focus}</span>}</>}
      note={`${rows.length - losers.length} profitable · ${losers.length} loss-making${losers.length ? ` (together ${fmtUsd(totalLoss)} / week)` : ''}.`}
      table={(
        <table className="viz-table"><thead><tr><th>Service</th><th>Agent</th><th>$ / week</th><th>Margin</th><th>Ports</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.id}><td>{r.id}</td><td>{r.agent || EM}</td><td>{fmtUsd(r.p)}</td><td>{r.margin != null ? fmtPct(r.margin) : EM}</td><td>{r.ports.length}</td></tr>)}</tbody>
        </table>
      )}
    >
      {({ show, hide }) => (
        <div ref={ref} className="viz-scroll">
          <svg width={W} height={H} role="img" aria-label="Weekly profit per selected service">
            {ticks.map((t) => (
              <g key={t}>
                <line x1={x(t)} x2={x(t)} y1={T - 4} y2={H} className={t === 0 ? 'viz-base' : 'viz-grid'} />
                <text x={x(t)} y={T - 7} className="viz-axis" textAnchor="middle">{usdAxis(t)}</text>
              </g>
            ))}
            {rows.map((r, i) => {
              const yy = T + i * ROW;
              const a = x(Math.min(0, r.p)); const b = x(Math.max(0, r.p));
              const labelIdx = i < 3 || i >= rows.length - 3;
              return (
                <g key={r.id} onMouseMove={(e) => show(e, [`Service ${r.id}`, `${fmtUsd(r.p)} / week`, r.rev != null ? `revenue ${fmtUsd(r.rev)} · cost ${fmtUsd(r.cost)}` : '', `${r.agent || EM} agent · ${r.ports.length} port calls`].filter(Boolean))} onMouseLeave={hide}>
                  <rect x={0} y={yy} width={W} height={ROW} fill="transparent" />
                  <text x={L - 6} y={yy + ROW - 4} className="viz-axis" textAnchor="end">{r.id.length > 15 ? `${r.id.slice(0, 14)}…` : r.id}</text>
                  <rect x={a} y={yy + 2} width={Math.max(1, b - a)} height={ROW - 4} rx={2} fill={r.p < 0 ? 'var(--viz-2)' : 'var(--viz-1)'} />
                  {labelIdx && <text x={r.p < 0 ? a - 4 : b + 4} y={yy + ROW - 4} className="viz-val" textAnchor={r.p < 0 ? 'end' : 'start'}>{fmtUsd(r.p)}</text>}
                </g>
              );
            })}
          </svg>
        </div>
      )}
    </ChartFrame>
  );
}

/* ── 4. Coverage by agent vs target, bullet ──────────────────────────────── */

export function AgentCoverage({ regions = {}, target = 70, exportBase = 'run' }) {
  const [ref, W] = useWidth();
  const [focus] = useAgentFocus();
  const rows = Object.values(regions).filter((r) => r && r.coverage != null)
    .map((r) => ({ agent: r.region || r.name, name: r.name || r.region, cov: Number(r.coverage), unserved: r.uncovered, services: r.services ?? r.selected }));
  if (!rows.length) return <div className="cx-compact-empty">No per-agent coverage in this run.</div>;
  const ROW = 34, L = 104, R = 118, T = 16;
  const H = T + rows.length * ROW + 18;
  const x = (v) => L + (W - L - R) * (Math.max(0, Math.min(100, v)) / 100);
  return (
    <ChartFrame
      exportName={`${exportBase}_coverage_by_agent`}
      exportTitle={`Demand coverage by agent vs ${target}% target`}
      csv={{ columns: [['agent', (r) => r.name], ['coverage_pct', (r) => r.cov], ['target_pct', () => target], ['unserved_teu', (r) => r.unserved], ['services', (r) => r.services]], rows }}
      legend={<><span><Sw c="var(--viz-1)" />Coverage</span><span><Sw c="var(--viz-ink)" shape="tick" />Target {target}%</span><span className="viz-hint">click an agent to filter every view</span></>}
      note={`${rows.filter((r) => r.cov >= target).length} of ${rows.length} agents meet the ${target}% coverage target.`}
      table={(
        <table className="viz-table"><thead><tr><th>Agent</th><th>Coverage</th><th>vs target</th><th>Unserved TEU</th><th>Services</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.agent}><td>{r.name}</td><td>{fmtPct(r.cov)}</td><td>{`${r.cov - target >= 0 ? '+' : '−'}${Math.abs(r.cov - target).toFixed(1)} pp`}</td><td>{r.unserved != null ? fmtNum(Math.round(r.unserved)) : EM}</td><td>{r.services ?? EM}</td></tr>)}</tbody>
        </table>
      )}
    >
      {({ show, hide }) => (
        <div ref={ref}>
          <svg width={W} height={H} role="img" aria-label={`Coverage by regional agent against the ${target}% target`}>
            {[0, 25, 50, 75, 100].map((t) => (
              <g key={t}>
                <line x1={x(t)} x2={x(t)} y1={T - 2} y2={H - 16} className="viz-grid" />
                <text x={x(t)} y={H - 3} className="viz-axis" textAnchor="middle">{t}%</text>
              </g>
            ))}
            {rows.map((r, i) => {
              const yy = T + i * ROW;
              const isF = sameAgent(focus, r.agent);
              const below = r.cov < target;
              return (
                <g key={r.agent} className={`viz-row ${isF ? 'is-focus' : ''} ${focus && !isF ? 'is-dim' : ''}`} role="button" tabIndex={0}
                  aria-pressed={!!isF} aria-label={`${r.name} ${fmtPct(r.cov)}; filter views to this agent`}
                  onClick={() => toggleAgentFocus(r.agent)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleAgentFocus(r.agent); } }}
                  onMouseMove={(e) => show(e, [`${r.name} agent`, `${fmtPct(r.cov)} of its demand served`, `${below ? 'below' : 'meets'} the ${target}% target (${(r.cov - target).toFixed(1)} pp)`, r.unserved != null ? `${fmtNum(Math.round(r.unserved))} TEU / week unserved` : '', isF ? 'Click to clear the filter' : 'Click to filter every view'].filter(Boolean))}
                  onMouseLeave={hide}>
                  <rect x={0} y={yy} width={W} height={ROW} className="viz-hit" />
                  <text x={L - 8} y={yy + ROW / 2 + 4} className="viz-label" textAnchor="end">{r.name}</text>
                  <rect x={x(0)} y={yy + 9} width={x(100) - x(0)} height={ROW - 18} rx={3} className="viz-track" />
                  <rect x={x(0)} y={yy + 9} width={Math.max(2, x(r.cov) - x(0))} height={ROW - 18} rx={3} fill="var(--viz-1)" />
                  <line x1={x(target)} x2={x(target)} y1={yy + 5} y2={yy + ROW - 5} className="viz-target" />
                  <text x={W - R + 8} y={yy + ROW / 2 + 4} className="viz-val">{fmtPct(r.cov)}<tspan className={below ? 'viz-st-below' : 'viz-st-met'}>{below ? ' ▼ below' : ' ✓ met'}</tspan></text>
                </g>
              );
            })}
          </svg>
        </div>
      )}
    </ChartFrame>
  );
}
