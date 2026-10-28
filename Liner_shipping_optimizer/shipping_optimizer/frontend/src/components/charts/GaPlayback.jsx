/**
 * GaPlayback — how each regional agent's service GA improved, generation by generation.
 *
 * Source: iteration_results[i].regional_results[j].ga_telemetry.generation_history (runs made from 2026-10-24;
 * ServiceGA records, after each generation, the population's best / mean / worst fitness, the best so far and
 * the services switched on in the best chromosome). Fitness is the GA's own surrogate: a weighted sum of
 * normalised objective components, unitless; it ranks candidate service sets inside one region and run and
 * is not comparable across regions.
 *
 * Play steps the cursor one generation at a time (a content change the viewer starts, so it runs at every
 * motion setting; nothing tweens). Runs without history say so and offer the run that has it.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { ChartFrame, useWidth } from './PlanCharts.jsx';
import { niceTicks } from '../../utils/benchStats.js';
import { setSelectedRun } from '../../services/runSelection.js';

const HISTORY_RUN = { kind: 'extra', id: 'worldsmall_seed00_20261024' };
const STEP_MS = 160;
const STOP_LABEL = {
  stagnation: 'stopped on stagnation',
  max_generations: 'ran all generations',
  time_limit: 'stopped on the time limit',
  max_runtime: 'stopped on the time limit',
};
const f3 = (v) => (v == null || !Number.isFinite(v) ? '—' : v.toFixed(3));
const Sw = ({ c, shape = 'line' }) => <span className={`viz-sw viz-sw--${shape}`} style={{ background: c, borderColor: c }} aria-hidden="true" />;

/** [{ iteration, regions: [{ name, history, telemetry }] }] for every iteration that recorded any history. */
export function gaHistoriesOf(raw) {
  const iters = (raw?.iteration_results || []).map((it, i) => ({ iteration: it?.iteration ?? i, results: it?.regional_results || [] }));
  if (!iters.length && raw?.regional_results) iters.push({ iteration: 0, results: raw.regional_results });
  return iters.map(({ iteration, results }) => ({
    iteration,
    regions: results.map((r, j) => ({
      name: r?.region || r?.agent || `region ${j + 1}`,
      history: r?.ga_telemetry?.generation_history || [],
      telemetry: r?.ga_telemetry || {},
    })).filter((r) => r.history.length > 0),
  })).filter((it) => it.regions.length > 0);
}

function Plot({ history, cursor, show, hide, onScrub }) {
  const [ref, W] = useWidth(560);
  const H = 220, L = 52, R = 12, T = 12, B = 30;
  const last = history[history.length - 1].gen || 1;
  const lo = Math.min(...history.map((g) => g.worst));
  const hi = Math.max(...history.map((g) => g.best));
  const ticks = niceTicks(lo, hi === lo ? lo + 1 : hi, 4);
  const y0 = Math.min(lo, ticks[0]); const y1 = Math.max(hi, ticks[ticks.length - 1]);
  const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : 1;
  const tickDec = step >= 1 ? 0 : Math.min(3, Math.ceil(-Math.log10(step)));
  const x = (g) => L + (W - L - R) * (g / last);
  const y = (v) => T + (H - T - B) * (1 - (v - y0) / (y1 - y0 || 1));
  const shown = history.filter((g) => g.gen <= cursor);
  const line = (key) => shown.map((g, i) => `${i ? 'L' : 'M'}${x(g.gen).toFixed(1)},${y(g[key]).toFixed(1)}`).join('');
  const band = shown.length
    ? `${shown.map((g, i) => `${i ? 'L' : 'M'}${x(g.gen).toFixed(1)},${y(g.best).toFixed(1)}`).join('')}${[...shown].reverse().map((g) => `L${x(g.gen).toFixed(1)},${y(g.worst).toFixed(1)}`).join('')}Z`
    : '';
  const cur = shown[shown.length - 1];
  const xTicks = niceTicks(0, last, Math.min(6, last)).filter((t) => Number.isInteger(t) && t <= last);
  const genAt = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    return Math.max(0, Math.min(last, Math.round(((px - L) / (W - L - R)) * last)));
  };
  return (
    <div ref={ref}>
      <svg width={W} height={H} role="img" aria-label={`Fitness by generation, ${history.length} generations; best ${f3(history[history.length - 1].best_so_far)}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="viz-grid" x1={L} x2={W - R} y1={y(t)} y2={y(t)} />
            <text className="viz-axis" x={L - 6} y={y(t) + 4} textAnchor="end">{t.toFixed(tickDec)}</text>
          </g>
        ))}
        <line className="viz-base" x1={L} x2={W - R} y1={H - B} y2={H - B} />
        {xTicks.map((t) => <text key={t} className="viz-axis" x={x(t)} y={H - B + 16} textAnchor="middle">{t}</text>)}
        <text className="viz-axis" x={W - R} y={H - 4} textAnchor="end">generation</text>
        <path d={band} className="ga-band" />
        <path d={line('mean')} className="ga-mean" />
        <path d={line('best')} className="ga-best" />
        {cur && (
          <g>
            <line className="ga-cursor" x1={x(cur.gen)} x2={x(cur.gen)} y1={T} y2={H - B} />
            <circle cx={x(cur.gen)} cy={y(cur.best)} r={4} className="ga-dot" />
          </g>
        )}
        <rect
          className="viz-hit" x={L} y={T} width={W - L - R} height={H - T - B} fill="transparent"
          onMouseMove={(e) => {
            const g = history.find((h) => h.gen === genAt(e));
            if (g) show(e, [`Generation ${g.gen}`, `best ${f3(g.best)} · mean ${f3(g.mean)}`, `worst ${f3(g.worst)}`, `services on ${g.services_on ?? '—'}`]);
          }}
          onMouseLeave={hide}
          onClick={(e) => onScrub(genAt(e))}
        />
      </svg>
    </div>
  );
}

export default function GaPlayback({ raw, selectedIteration = 0 }) {
  const iters = useMemo(() => gaHistoriesOf(raw), [raw]);
  const [iterSel, setIterSel] = useState(null);
  const [regionIdx, setRegionIdx] = useState(0);
  const it = iters.find((x) => x.iteration === (iterSel ?? selectedIteration)) || iters[0] || null;
  const region = it?.regions[Math.min(regionIdx, (it?.regions.length || 1) - 1)] || null;
  const history = region?.history || [];
  const last = history.length ? history[history.length - 1].gen : 0;
  const [cursor, setCursor] = useState(last);
  const [playing, setPlaying] = useState(false);

  // A new series shows complete; play starts again from generation 0.
  useEffect(() => { setCursor(last); setPlaying(false); }, [region, last]);
  useEffect(() => {
    if (!playing) return undefined;
    if (cursor >= last) { setPlaying(false); return undefined; }
    const t = setTimeout(() => setCursor((c) => Math.min(last, c + 1)), STEP_MS);
    return () => clearTimeout(t);
  }, [playing, cursor, last]);

  if (!iters.length) {
    return (
      <div className="ga-empty">
        <p>This run does not record the GA's generations: runs made before 24 Oct 2026 keep only the final telemetry (generations executed, stop reason, best fitness).</p>
        <button type="button" className="cmp-btn" onClick={() => setSelectedRun(HISTORY_RUN)}>Open the 24 Oct run with GA history</button>
        <p className="ga-empty-note">It needs the backend (runs_extra/). The GA itself is unchanged; recording the history was proven not to alter its result.</p>
      </div>
    );
  }

  const tel = region.telemetry;
  const cur = history.find((g) => g.gen === cursor) || history[history.length - 1];
  const first = history[0];
  const gain = cur.best_so_far - first.best_so_far;
  const play = () => { if (cursor >= last) setCursor(0); setPlaying(true); };

  return (
    <div className="ga-play">
      <div className="ga-controls">
        {iters.length > 1 && (
          <label className="ga-field">
            <span>Iteration</span>
            <select value={it.iteration} onChange={(e) => { setIterSel(Number(e.target.value)); }}>
              {iters.map((x) => <option key={x.iteration} value={x.iteration}>{`iter ${String(x.iteration).padStart(2, '0')}${x.iteration === selectedIteration ? ' · selected' : ''}`}</option>)}
            </select>
          </label>
        )}
        <div className="viz-toggle" role="group" aria-label="Regional agent">
          {it.regions.map((r, j) => (
            <button key={r.name} type="button" aria-pressed={r === region} onClick={() => setRegionIdx(j)}>{r.name}</button>
          ))}
        </div>
        <div className="ga-transport">
          <button type="button" className="cmp-btn" onClick={playing ? () => setPlaying(false) : play} aria-pressed={playing}>
            {playing ? '❚❚ Pause' : cursor >= last ? '▶ Replay' : '▶ Play'}
          </button>
          <input
            type="range" min={0} max={last} step={1} value={cursor}
            onChange={(e) => { setPlaying(false); setCursor(Number(e.target.value)); }}
            aria-label="Generation"
          />
          <span className="ga-gen" aria-live="polite">gen {cursor} / {last}</span>
        </div>
      </div>

      <div className="ga-readout">
        <div><span className="k">best</span><span className="v">{f3(cur.best)}</span></div>
        <div><span className="k">mean</span><span className="v">{f3(cur.mean)}</span></div>
        <div><span className="k">worst</span><span className="v">{f3(cur.worst)}</span></div>
        <div><span className="k">best so far</span><span className="v">{f3(cur.best_so_far)}</span></div>
        <div><span className="k">services on</span><span className="v">{cur.services_on ?? '—'}</span></div>
        <div><span className="k">gain vs gen 0</span><span className="v">{gain >= 0 ? '+' : ''}{f3(gain)}</span></div>
      </div>

      <ChartFrame
        exportName={`ga_${region.name}_iter${it.iteration}`}
        exportTitle={`Service GA fitness by generation · ${region.name} · iteration ${it.iteration}`}
        legend={<>
          <span><Sw c="var(--viz-1)" />Best in population</span>
          <span><Sw c="var(--viz-muted)" />Mean</span>
          <span><Sw c="var(--viz-track)" shape="bar" />Worst to best</span>
        </>}
        csv={{ columns: [['generation', (g) => g.gen], ['best', (g) => g.best], ['mean', (g) => g.mean], ['worst', (g) => g.worst], ['best_so_far', (g) => g.best_so_far], ['services_on', (g) => g.services_on]], rows: history }}
        table={(
          <table className="viz-table">
            <thead><tr><th>Gen</th><th>Best</th><th>Mean</th><th>Worst</th><th>Best so far</th><th>Services on</th></tr></thead>
            <tbody>{history.map((g) => <tr key={g.gen}><td>{g.gen}</td><td>{f3(g.best)}</td><td>{f3(g.mean)}</td><td>{f3(g.worst)}</td><td>{f3(g.best_so_far)}</td><td>{g.services_on ?? '—'}</td></tr>)}</tbody>
          </table>
        )}
        note={`${tel.actual_generations_executed ?? last} of ${tel.max_generations ?? '—'} generations, ${STOP_LABEL[tel.early_stop_reason] || tel.early_stop_reason || 'stop reason not recorded'}${tel.stagnation_limit ? ` (limit ${tel.stagnation_limit} generations without improvement)` : ''}${tel.runtime_seconds != null ? ` in ${Number(tel.runtime_seconds).toFixed(2)} s` : ''}. Fitness is the GA's unitless surrogate (weighted, normalised objectives); it ranks service sets within this region only.`}
      >
        {({ show, hide }) => <Plot history={history} cursor={cursor} show={show} hide={hide} onScrub={(g) => { setPlaying(false); setCursor(g); }} />}
      </ChartFrame>
    </div>
  );
}
