/**
 * RunDiff.jsx — two plans side by side: what changed between runs, seeds or iterations of one dataset.
 *
 * Pick plan A and plan B (any run in the catalog — latest local run, runs_extra, benchmark seeds — and either
 * its final plan or one iteration). Services are matched by rotation + vessel class (utils/runDiff.js), so a
 * service that came back under a new id still counts as kept. Shows KPI and cost-line deltas, the routes on
 * one map (B only / A only / both) or split screen (A | B, cameras linked: design D7), and the service list with
 * what happened to each.
 *
 * Without the backend only the latest local run is available; its iterations can still be compared.
 */

import React, { useEffect, useMemo, useState } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import WorldMap from '../../components/map/WorldMap.jsx';
import { Provenance } from '../../components/console/p12.jsx';
import { SourceChip } from '../../components/common/Figure.jsx';
import { apiClient } from '../../services/apiClient.js';
import { getSelectedRun, runKey, runOutputUrl } from '../../services/runSelection.js';
import { useScenarioIntent } from '../../services/scenarioIntent.js';
import { toast } from '../../services/toastStore.js';
import { planOf, planKpis, diffPlans, diffOverlay, diffSide } from '../../utils/runDiff.js';
import { fmtNum, fmtPct, fmtUsd } from '../../utils/formatters.js';
import { downloadCsv } from '../../utils/exportData.js';

const outputs = new Map();   // run key → Promise<pipeline_output | null>
function loadOutput(run) {
  const k = runKey(run);
  if (!outputs.has(k)) {
    outputs.set(k, fetch(runOutputUrl(run)).then((r) => (r.ok ? r.json() : null)).catch(() => null)
      .then((d) => { if (!d) outputs.delete(k); return d; }));
  }
  return outputs.get(k);
}

const datasetOfRaw = (raw, run) => String(
  (run?.kind === 'benchmark' && run.dataset) || raw?.dataset_run?.dataset || raw?.test_scorecard?.dataset_run?.dataset || 'WorldSmall',
).toLowerCase();

const MAP_MODE_KEY = 'liner.runDiff.mapMode';

const STATUS = {
  added:   { label: 'only in B', tone: 'var(--viz-1)' },
  removed: { label: 'only in A', tone: 'var(--viz-2)' },
  changed: { label: 'vessel class changed', tone: 'var(--viz-muted)' },
  retimed: { label: 'departures changed', tone: 'var(--viz-muted)' },
  kept:    { label: 'in both', tone: 'var(--viz-muted)' },
};
const FILTERS = ['all', 'added', 'removed', 'changed', 'retimed', 'kept'];
const COST_ROWS = [
  ['revenue', 'Revenue', 'up'], ['vessel_cost', 'Vessel hire', 'down'], ['fuel', 'Fuel', 'down'],
  ['port_call_cost', 'Port calls', 'down'], ['handling', 'Handling', 'down'], ['transshipment', 'Transshipment', 'down'],
  ['cost', 'Total cost', 'down'], ['profit', 'Profit', 'up'],
];
const sgn = (v, f = fmtUsd) => (v == null ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : '±'}${f(Math.abs(v))}`);
const toneOf = (d, good) => (d == null || Math.abs(d) < 1e-6 ? '' : (d > 0) === (good === 'up') ? 'is-good' : 'is-bad');

function useCatalog() {
  const [catalog, setCatalog] = useState(null);
  useEffect(() => {
    let off = false;
    apiClient.getRuns().then((c) => { if (!off) setCatalog(c); }).catch(() => { if (!off) setCatalog({ current: null, benchmark: [], extra: [] }); });
    return () => { off = true; };
  }, []);
  return useMemo(() => {
    const opts = [{ key: 'current', label: 'Latest local run', run: { kind: 'current' }, dataset: null }];
    (catalog?.extra || []).forEach((r) => opts.push({ key: `extra:${r.id}`, label: r.label, run: { kind: 'extra', id: r.id }, dataset: String(r.dataset || '').toLowerCase() || null, group: 'Other runs' }));
    (catalog?.benchmark || []).forEach((g) => g.seeds.filter((s) => s.has_pipeline_output).forEach((s) => opts.push({
      key: `${g.key}/${s.seed}`, label: `${g.dataset} · seed ${String(s.seed).padStart(2, '0')}`,
      run: { kind: 'benchmark', dataset: g.key, seed: s.seed }, dataset: String(g.dataset).toLowerCase(), group: `${g.dataset} · 30-seed benchmark`,
    })));
    return { opts, loaded: catalog != null };
  }, [catalog]);
}

function usePlanSource(sel) {
  const [raw, setRaw] = useState(undefined);
  useEffect(() => {
    let off = false;
    setRaw(undefined);
    if (sel) loadOutput(sel.run).then((d) => { if (!off) setRaw(d || null); });
    return () => { off = true; };
  }, [sel && runKey(sel.run)]);   // eslint-disable-line react-hooks/exhaustive-deps
  return raw;
}

function PlanPicker({ side, opts, value, onRun, iteration, onIteration, raw }) {
  const iters = (raw?.iteration_results || []).map((it, i) => it?.iteration ?? i);
  const finalIter = raw?.network_ledger?.iteration;
  const groups = [...new Set(opts.filter((o) => o.group).map((o) => o.group))];
  return (
    <div className="rd-pick">
      <span className={`rd-side is-${side.toLowerCase()}`}>{side}</span>
      <select aria-label={`Run for plan ${side}`} value={value} onChange={(e) => onRun(e.target.value)}>
        {opts.filter((o) => !o.group).map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
        {groups.map((g) => (
          <optgroup key={g} label={g}>
            {opts.filter((o) => o.group === g).map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
          </optgroup>
        ))}
      </select>
      <select aria-label={`Plan of run ${side}`} value={iteration == null ? 'final' : String(iteration)} onChange={(e) => onIteration(e.target.value === 'final' ? null : Number(e.target.value))} disabled={!raw}>
        <option value="final">{`Final plan${finalIter != null ? ` (iter ${String(finalIter).padStart(2, '0')})` : ''}`}</option>
        {iters.map((i) => <option key={i} value={i}>{`Iteration ${String(i).padStart(2, '0')}`}</option>)}
      </select>
    </div>
  );
}

export default function RunDiff() {
  const { opts, loaded } = useCatalog();
  const initial = getSelectedRun();
  const [aKey, setAKey] = useState(runKey(initial));
  const [bKey, setBKey] = useState(runKey(initial));
  const [aIter, setAIter] = useState(null);
  const [bIter, setBIter] = useState(undefined);   // undefined: pick a default once B's run has loaded
  const [filter, setFilter] = useState('all');
  const [mapMode, setMapModeState] = useState(() => { try { return localStorage.getItem(MAP_MODE_KEY) === 'split' ? 'split' : 'overlay'; } catch (_) { return 'overlay'; } });
  const setMapMode = (m) => { setMapModeState(m); try { localStorage.setItem(MAP_MODE_KEY, m); } catch (_) { /* private window */ } };

  // "compare with seed 7" from the command palette (design D10): A = the run on screen (final plan), B = that seed
  // of the same dataset. The catalog may still be loading, so the request waits for it.
  const [seedAsk, setSeedAsk] = useState(null);
  useScenarioIntent('diff', (it) => setSeedAsk(it.seed));

  const optOf = (k) => opts.find((o) => o.key === k) || (k === runKey(initial) ? { key: k, run: initial, label: k } : opts[0]);
  const aOpt = optOf(aKey); const bOpt = optOf(bKey);
  const aRaw = usePlanSource(aOpt); const bRaw = usePlanSource(bOpt);

  // Default B: another iteration of the same run (the first that is not its final plan), else its final plan.
  useEffect(() => {
    if (bIter !== undefined || !bRaw) return;
    const fin = bRaw.network_ledger?.iteration;
    const other = (bRaw.iteration_results || []).map((it, i) => it?.iteration ?? i).find((i) => i !== fin);
    setBIter(aKey === bKey && aIter == null && other != null ? other : null);
  }, [bRaw, bIter, aKey, bKey, aIter]);

  const dsA = aRaw ? datasetOfRaw(aRaw, aOpt.run) : null;
  const dsB = bRaw ? datasetOfRaw(bRaw, bOpt.run) : null;
  const sameDs = dsA && dsB && dsA === dsB;
  useEffect(() => {
    if (seedAsk == null || !loaded) return;
    const onScreen = runKey(initial);
    if (aKey !== onScreen || aIter != null) { setAKey(onScreen); setAIter(null); return; }   // A first, then its dataset
    if (!aRaw) return;
    const hit = opts.find((o) => o.run.kind === 'benchmark' && o.run.seed === seedAsk && o.run.dataset === dsA);
    if (hit) { setBKey(hit.key); setBIter(null); toast(`Run diff: on screen (A) against ${hit.label} (B)`); }
    else toast(`No seed ${seedAsk} with a saved plan for ${dsA} in the catalog`, { tone: 'warn' });
    setSeedAsk(null);
  }, [seedAsk, loaded, aKey, aIter, aRaw, dsA]); // eslint-disable-line react-hooks/exhaustive-deps
  const planA = useMemo(() => (aRaw ? planOf(aRaw, aIter) : null), [aRaw, aIter]);
  const planB = useMemo(() => (bRaw && bIter !== undefined ? planOf(bRaw, bIter) : null), [bRaw, bIter]);
  const ready = planA && planB && sameDs;
  const diff = useMemo(() => (ready ? diffPlans(planA, planB) : null), [ready, planA, planB]);
  const kA = useMemo(() => planKpis(planA), [planA]);
  const kB = useMemo(() => planKpis(planB), [planB]);
  const overlay = useMemo(() => (diff ? diffOverlay(diff.rows) : null), [diff]);
  const sideA = useMemo(() => (diff && mapMode === 'split' ? diffSide(diff.rows, 'A') : null), [diff, mapMode]);
  const sideB = useMemo(() => (diff && mapMode === 'split' ? diffSide(diff.rows, 'B') : null), [diff, mapMode]);
  const rows = useMemo(() => (diff ? diff.rows.filter((r) => filter === 'all' || r.status === filter).sort((x, y) => Math.abs(y.dProfit) - Math.abs(x.dProfit)) : []), [diff, filter]);
  const samePlan = aKey === bKey && aIter === bIter;

  const nameOf = (o, it) => `${o?.label || '—'} · ${it == null ? 'final plan' : `iteration ${String(it).padStart(2, '0')}`}`;
  const swap = () => { setAKey(bKey); setBKey(aKey); setAIter(bIter ?? null); setBIter(aIter); };

  return (
    <div className="cx-page-body space-y-3">
      <PageHead
        section="Benchmarks"
        eyebrow="Run diff"
        title="Run diff"
        subtitle="Compare two plans of one dataset: runs, benchmark seeds or iterations of a run. Services are matched by rotation and vessel class, so a service that returns under a new id still counts as kept."
        pills={[
          { tone: loaded && opts.length > 1 ? 'available' : 'no_data', label: loaded ? `${opts.length} run${opts.length === 1 ? '' : 's'} to compare` : 'loading runs…' },
          diff ? { tone: 'selected', label: `${diff.counts.added || 0} added · ${diff.counts.removed || 0} removed` } : { tone: 'no_data', label: 'no comparison yet' },
        ]}
      />

      <InstrumentPanel title="Plans" right={<span className="text-[12px] text-slate-400">{opts.length === 1 ? 'only the latest run without the backend; its iterations can still be compared' : 'same dataset only'}</span>}>
        <div className="rd-picks">
          <PlanPicker side="A" opts={opts} value={aKey} onRun={(k) => { setAKey(k); setAIter(null); }} iteration={aIter} onIteration={setAIter} raw={aRaw} />
          <button type="button" className="cmp-btn" onClick={swap} aria-label="Swap plans A and B" title="Swap A and B">⇄</button>
          <PlanPicker side="B" opts={opts} value={bKey} onRun={(k) => { setBKey(k); setBIter(null); }} iteration={bIter ?? null} onIteration={setBIter} raw={bRaw} />
        </div>
        {(aRaw === null || bRaw === null) && <p className="rd-warn">A run's output could not be loaded (benchmark and kept runs need the backend).</p>}
        {aRaw && bRaw && !sameDs && <p className="rd-warn">A is {dsA}, B is {dsB}: plans of different datasets serve different demand, so they are not compared. Pick runs of one dataset.</p>}
        {ready && samePlan && <p className="rd-warn">A and B are the same plan; pick another run or iteration for B.</p>}
      </InstrumentPanel>

      {ready && (
        <>
          <div className="wi-kpis">
            {[
              ['Weekly profit', 'profit', fmtUsd, 'up', 'revenue − cost, $/week'], ['Coverage', 'coverage_pct', (v) => fmtPct(v), 'up', 'TEU served ÷ weekly demand'],
              ['TEU carried / wk', 'served_teu', fmtNum, 'up', 'recorded flows of each run'], ['Services', 'services', fmtNum, null, 'services in the plan'],
              ['Departures / wk', 'departures', fmtNum, null, 'Σ service frequency'], ['Vessels', 'vessels', fmtNum, null, 'Σ vessels deployed'],
              ['Transshipped TEU / wk', 'transship_teu', (v) => fmtNum(Math.round(v)), null, 'TEU of flows riding 2+ services'], ['Transfer hubs', 'transship_hubs', fmtNum, null, 'ports where cargo changes ship'],
            ].map(([k, f, fmt, good, def]) => {
              const d = kA[f] != null && kB[f] != null ? kB[f] - kA[f] : null;
              const dTxt = f === 'coverage_pct' && d != null ? `${d >= 0 ? '+' : '−'}${Math.abs(d).toFixed(1)} pp` : sgn(d, fmt);
              return (
                <div key={f} className="wi-kpi">
                  <div className="k">{k}</div>
                  <div className="v">{kB[f] != null ? fmt(kB[f]) : '—'}</div>
                  <div className={`d ${good ? toneOf(d, good) : ''}`}>{dTxt} <span>vs A {kA[f] != null ? fmt(kA[f]) : '—'}</span></div>
                  <SourceChip src="Run files A · B" def={def} />
                </div>
              );
            })}
          </div>

          <div className="grid grid-cols-12 gap-3 items-stretch">
            <div className={`col-span-12 ${mapMode === 'split' ? '' : 'xl:col-span-8'} min-w-0`}>
              <InstrumentPanel title="Routes that changed" bodyPadding="flush"
                right={(
                  <span className="rd-maphead">
                    <span className="text-[12px] text-slate-400">{mapMode === 'split' ? 'A | B · cameras linked' : 'B only · A only (dashed) · both'}</span>
                    <span className="mk-toggle" role="group" aria-label="Map layout">
                      <button type="button" className="cmp-btn" aria-pressed={mapMode === 'overlay'} onClick={() => setMapMode('overlay')}>Overlay</button>
                      <button type="button" className="cmp-btn" aria-pressed={mapMode === 'split'} onClick={() => setMapMode('split')}>Split A | B</button>
                    </span>
                  </span>
                )}>
                {mapMode === 'split' ? (
                  <div className="rd-split">
                    {[['A', sideA, nameOf(aOpt, aIter)], ['B', sideB, nameOf(bOpt, bIter)]].map(([side, d, name]) => (
                      <figure key={side} className="rd-split-pane" aria-label={`Plan ${side}: ${name}`}>
                        <figcaption><b>{side}</b> {name} <span>{d.services.length} services</span></figcaption>
                        <div className="rd-split-map">
                          <WorldMap optimizationState={null} selectedServices={d.services} diff={d.status} diffSide={side} fitPorts={d.fitPorts}
                            syncGroup="rundiff" dataset={dsA || undefined} drawKey={`diff${side}|${aKey}|${aIter}|${bKey}|${bIter}`} />
                        </div>
                      </figure>
                    ))}
                  </div>
                ) : (
                  <div style={{ height: 420 }}>
                    <WorldMap optimizationState={null} selectedServices={overlay.services} diff={overlay.status} dataset={dsA || undefined}
                      drawKey={`diff|${aKey}|${aIter}|${bKey}|${bIter}`} />
                  </div>
                )}
              </InstrumentPanel>
            </div>
            <div className={`col-span-12 ${mapMode === 'split' ? 'xl:col-span-6' : 'xl:col-span-4'} min-w-0`}>
              <InstrumentPanel title="Weekly money, A → B">
                <table className="viz-table wi-table">
                  <thead><tr><th>Line</th><th className="r">A</th><th className="r">B</th><th className="r">B − A</th></tr></thead>
                  <tbody>
                    {COST_ROWS.map(([f, label, good]) => {
                      const d = kA[f] != null && kB[f] != null ? kB[f] - kA[f] : null;
                      return (
                        <tr key={f} className={f === 'profit' || f === 'cost' ? 'is-total' : ''}>
                          <td>{label}</td><td className="r">{fmtUsd(kA[f])}</td><td className="r">{fmtUsd(kB[f])}</td>
                          <td className={`r ${toneOf(d, good)}`}>{sgn(d)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <ul className="rd-counts">
                  {['added', 'removed', 'changed', 'retimed', 'kept'].map((s) => (
                    <li key={s}><span className="rd-sw" style={{ background: STATUS[s].tone }} aria-hidden="true" />{STATUS[s].label}<b>{diff.counts[s] || 0}</b></li>
                  ))}
                </ul>
              </InstrumentPanel>
            </div>
          </div>

          <InstrumentPanel
            title={`Services (${rows.length})`}
            right={(
              <div className="flex items-center gap-2 flex-wrap justify-end">
                <button type="button" className="cmp-btn" onClick={() => downloadCsv('run_diff_services', [
                  ['status', (r) => r.status], ['rotation', (r) => r.rot.replace(/>/g, ' ')], ['id_a', (r) => r.a?.id], ['id_b', (r) => r.b?.id],
                  ['class_a', (r) => r.a?.vessel_class], ['class_b', (r) => r.b?.vessel_class], ['departures_a', (r) => r.a?.frequency_per_week], ['departures_b', (r) => r.b?.frequency_per_week],
                  ['profit_a_usd', (r) => r.a?.weekly_profit], ['profit_b_usd', (r) => r.b?.weekly_profit], ['delta_usd', (r) => r.dProfit],
                ], rows)}>CSV</button>
              </div>
            )}
            bodyPadding="flush"
          >
            <div className="rd-filters" role="group" aria-label="Filter by change">
              {FILTERS.map((f) => (
                <button key={f} type="button" className="cmp-btn" aria-pressed={filter === f} onClick={() => setFilter(f)} disabled={f !== 'all' && !diff.counts[f]}>
                  {f === 'all' ? `All (${diff.rows.length})` : `${STATUS[f].label} (${diff.counts[f] || 0})`}
                </button>
              ))}
            </div>
            <div className="rd-table-wrap">
              <table className="viz-table rd-table">
                <thead>
                  <tr><th>Change</th><th>Rotation</th><th>Vessel class</th><th className="r">Dep./wk</th><th className="r">Profit A</th><th className="r">Profit B</th><th className="r">B − A</th></tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i}>
                      <td><span className="rd-sw" style={{ background: STATUS[r.status].tone }} aria-hidden="true" />{STATUS[r.status].label}</td>
                      <td className="rd-rot" title={`A ${r.a?.id || '—'} · B ${r.b?.id || '—'}`}>{(r.b || r.a).ports.join(' → ')}</td>
                      <td>{r.a && r.b && r.a.vessel_class !== r.b.vessel_class ? `${r.a.vessel_class} → ${r.b.vessel_class}` : (r.b || r.a).vessel_class}</td>
                      <td className="r">{r.a && r.b && r.a.frequency_per_week !== r.b.frequency_per_week ? `${r.a.frequency_per_week} → ${r.b.frequency_per_week}` : (r.b || r.a).frequency_per_week}</td>
                      <td className="r">{r.a ? fmtUsd(r.a.weekly_profit) : '—'}</td>
                      <td className="r">{r.b ? fmtUsd(r.b.weekly_profit) : '—'}</td>
                      <td className={`r ${toneOf(r.dProfit, 'up')}`}>{sgn(r.dProfit)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </InstrumentPanel>

          <div className="viz-note">
            A = {nameOf(aOpt, aIter)}; B = {nameOf(bOpt, bIter)}. Money and coverage are each plan's own ledger figures; service profit is
            the ledger's per-service attribution, so a service's change can come from cargo moving between services, not only from the service itself.
          </div>
        </>
      )}

      <Provenance
        source="pipeline_output.json of each plan (selected_services + network_ledger, or iteration_results[i])"
        sourceStatus={ready ? 'available' : 'no_data'}
        attribution="Read-only comparison of recorded plans"
        license="Internal artifact"
        recordCount={diff ? diff.rows.length : 0}
      />
    </div>
  );
}
