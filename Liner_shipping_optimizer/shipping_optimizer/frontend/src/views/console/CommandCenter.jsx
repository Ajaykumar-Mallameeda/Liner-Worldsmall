/**
 * CommandCenter.jsx
 * -----------------
 * Overview of one optimizer run: system state, the selected iteration's KPIs, the route map,
 * LLM diagnostics, iteration progress and a derived activity log.
 *
 * Rules:
 * - The selected iteration is the run's own answer (consoleSelectors.selectedIterationOf); clicking another
 *   iteration INSPECTS it: a banner says so and every KPI on the page switches to that iteration.
 * - Every figure comes from the run on disk. A missing figure shows as "—", never as a placeholder number.
 */

import React, { useState, useMemo, useEffect } from 'react';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import MapCanvas from '../../components/console/MapCanvas.jsx';
import LlmDiagnosticsPanel from '../../components/console/LlmDiagnosticsPanel.jsx';
import VsMean from '../../components/common/VsMean.jsx';
import { UnitValue, Sparkline, Provenance } from '../../components/common/Figure.jsx';
import ComparePanel from '../../components/console/ComparePanel.jsx';
import { useBenchBaseline } from '../../services/benchBaseline.js';
import { CostWaterfall, ProfitCoverage, ServicePnl, AgentCoverage } from '../../components/charts/PlanCharts.jsx';
import { fmtNum, fmtPct, fmtUsd } from '../../utils/formatters.js';
import {
  buildProfitSeries,
  buildCoverageSeries,
  buildScoreSeries,
  selectedIterationOf,
  liveLinkOf,
  datasetKeyOf,
} from '../../runtime/consoleSelectors.js';

const EM = '—';
const pad2 = (n) => String(n).padStart(2, '0');
const num = (v) => (v == null || Number.isNaN(Number(v)) ? null : Number(v));
const titleCase = (s) => (s ? String(s).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : s);

function sparkPoints(values, top, span) {
  if (!values.length) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max === min ? 1 : max - min;
  return values.map((v, idx) => ({ x: 15 + idx * 35, y: parseFloat((top - ((v - min) / range) * span).toFixed(1)) }));
}

export default function CommandCenter({
  optimizationState,
  maritimeOverview,
  runtime,
}) {
  const optState = (runtime && runtime.global) ? runtime : optimizationState;
  const sm = optState?.global || {};
  const raw = optState?.raw || {};
  const [userSelectedIter, setUserSelectedIter] = useState(null);
  const [region, setRegion] = useState('world');
  const [comparing, setComparing] = useState(false);
  useEffect(() => {
    const open = () => setComparing(true);
    window.addEventListener('vr:compare', open);
    return () => window.removeEventListener('vr:compare', open);
  }, []);

  const canonicalSel = selectedIterationOf(optState);
  const scorecards = raw.iteration_selection?.scorecards || optState?.scorecards || [];
  const audit = raw.iteration_audit || sm.iteration_audit || [];
  const rawIterResults = raw.iteration_results || optState?.iteration_results || [];

  // One row per iteration, from the selection scorecards (fallback: normalized iterations).
  const iterationsResolved = useMemo(() => {
    const auditBy = new Map(audit.map((a) => [a.iteration, a]));
    if (scorecards.length > 0) {
      return scorecards.map((sc, idx) => {
        const it = sc.iteration ?? idx;
        const a = auditBy.get(it) || {};
        return {
          iter: it,
          profit: num(sc.weekly_profit),
          coverage: num(sc.global_demand_weighted_coverage),
          regionalCoverage: num(sc.average_regional_coverage),
          score: num(sc.convergence_score),
          satisfiedDemand: num(sc.satisfied_demand),
          unservedDemand: num(sc.unserved_demand),
          servicesDeployed: num(sc.services_deployed),
          marginPct: num(sc.profit_margin_pct),
          rerun: a.needs_rerun ?? null,
        };
      });
    }
    return (optState?.iterations || []).map((it, idx) => ({
      iter: it.iter ?? idx,
      profit: num(it.profit),
      coverage: num(it.globalCoverage ?? it.coverage),
      regionalCoverage: num(it.coverage),
      score: num(it.score),
      satisfiedDemand: num(it.satisfiedDemand),
      unservedDemand: num(it.unservedDemand),
      servicesDeployed: num(it.servicesDeployed),
      marginPct: num(it.marginPct),
      rerun: it.rerun ?? null,
    }));
  }, [scorecards, audit, optState?.iterations]);

  const lastIter = iterationsResolved.length ? iterationsResolved[iterationsResolved.length - 1].iter : null;
  const baseSel = canonicalSel ?? lastIter;
  const viewIterNum = userSelectedIter ?? baseSel;
  const inspecting = userSelectedIter != null && userSelectedIter !== canonicalSel;
  const viewIter = iterationsResolved.find((i) => i.iter === viewIterNum) || null;

  // Services drawn on the map: the viewed iteration's, else the run's final selection.
  const viewServices = useMemo(() => {
    const r = rawIterResults.find((x) => (x.iteration ?? null) === viewIterNum);
    if (r?.selected_services?.length) return r.selected_services;
    return sm.selected_services || [];
  }, [rawIterResults, viewIterNum, sm.selected_services]);

  // KPIs: the viewed iteration's scorecard; the run summary only for the selected iteration.
  const useSummary = !inspecting;
  const weeklyProfit = viewIter?.profit ?? (useSummary ? sm.weeklyProfit : null);
  const coverage = viewIter?.coverage ?? (useSummary ? sm.coverage : null);
  const teuServed = viewIter?.satisfiedDemand ?? (useSummary ? sm.satisfiedDemand : null);
  const unservedTeu = viewIter?.unservedDemand ?? (useSummary ? sm.unserved : null);
  const score = viewIter?.score;
  const servicesCount = viewServices.length || viewIter?.servicesDeployed || null;

  const viewRegions = useMemo(() => {
    const m = optState?.iteration_regions_map || {};
    return (viewIterNum != null && m[viewIterNum] && Object.keys(m[viewIterNum]).length) ? m[viewIterNum] : (optState?.regions || {});
  }, [optState?.iteration_regions_map, optState?.regions, viewIterNum]);
  const regionCount = Object.keys(viewRegions).length || null;

  const lowestCovRegion = useMemo(() => {
    const regs = Object.values(viewRegions);
    if (!regs.length) return null;
    return [...regs]
      .filter((r) => r.coverage != null)
      .sort((a, b) => Number(a.coverage) - Number(b.coverage))[0] || null;
  }, [viewRegions]);

  // Weekly cost lines of the selected run (summary_metrics); operating = vessel operating cost.
  const costLines = [
    ['operating', sm.operatingCost],
    ['fuel', sm.fuelCost],
    ['port', sm.portCost],
    ['transshipment', sm.transshipCost],
  ].filter(([, v]) => v != null);
  const totalCost = sm.totalCost ?? (costLines.length ? costLines.reduce((s, [, v]) => s + Number(v), 0) : null);
  const profitPerService = weeklyProfit != null && servicesCount ? weeklyProfit / servicesCount : null;
  const costPerService = !inspecting && totalCost != null && servicesCount ? totalCost / servicesCount : null;

  const profitPts = useMemo(() => sparkPoints(buildProfitSeries(iterationsResolved), 30, 20), [iterationsResolved]);
  const covPts = useMemo(() => sparkPoints(buildCoverageSeries(iterationsResolved), 28, 16), [iterationsResolved]);
  const scorePts = useMemo(() => sparkPoints(buildScoreSeries(iterationsResolved), 26, 16), [iterationsResolved]);

  const outcome = String(sm.health_status?.status || sm.status || '').toLowerCase();
  const outcomeLabel = outcome ? outcome.toUpperCase() : EM;
  const link = liveLinkOf(optimizationState);
  const runLabel = optState?.source?.label || sm.run_id || EM;
  const selectionMethod = raw.iteration_selection?.selection_method || sm.iteration_selection?.selection_method;
  const runtimeSec = num(sm.runtime) || num(sm.health_status?.runtime_seconds);
  const verdict = sm.decision_output?.evaluation?.status;
  // Frozen 30-seed benchmark of the same dataset: the yardstick for the headline figures.
  const bench = useBenchBaseline(datasetKeyOf(optState));
  const marginPct = viewIter?.marginPct ?? (useSummary ? num(sm.margin) : null);
  // Where each headline figure is read from, for the provenance popovers and the per-iteration sparklines.
  const viewIdx = iterationsResolved.findIndex((i) => i.iter === viewIterNum);
  const series = (k) => iterationsResolved.map((i) => i[k]);
  const fromCards = scorecards.length > 0 && viewIter != null;
  const provOf = (field, summaryField) => [
    ['File', optState?.source?.url || 'pipeline_output.json'],
    ['Field', fromCards ? `iteration_selection.scorecards[iter ${viewIterNum}].${field}` : summaryField],
    ['Run', runLabel],
    ['File time', optState?.source?.modifiedIso ? optState.source.modifiedIso.replace('T', ' ').slice(0, 16) + ' UTC' : null],
    ['Benchmark', bench ? `/api/benchmark/${bench.dataset}/seeds · ${bench.n} seeds${bench.excluded ? ` (${bench.excluded} left out)` : ''}` : 'none for this dataset'],
  ];

  return (
    <div className="cx-page-body cc-body-full">
      {inspecting && (
        <div className="cx-inspect-banner" role="status">
          <span>
            Inspecting <b>iter {pad2(viewIterNum)}</b>. The run selected <b>iter {canonicalSel != null ? pad2(canonicalSel) : EM}</b>; every figure below is for iter {pad2(viewIterNum)}.
          </span>
          <button type="button" onClick={() => setUserSelectedIter(null)}>Back to selected</button>
        </div>
      )}

      {/* ══ TOP ROW: SYSTEM STATE + CURRENT DECISION ══ */}
      <div className="cc-top-row">
        <div className="cc-top-row-state">
          <InstrumentPanel
            title="System State"
            right={<span className={`font-semibold uppercase text-[12px] tracking-wider ${outcome === 'completed' ? 'text-emerald-400' : 'text-amber-400'}`}>{outcomeLabel}</span>}
          >
            <div className="cc-system-state-table">
              <div className="cc-ss-row">
                <span className="cc-ss-k">RUN</span>
                <span className="cc-ss-v text-slate-200 font-mono" title={runLabel}>{runLabel}</span>
              </div>
              <div className="cc-ss-row">
                <span className="cc-ss-k">AGENTS</span>
                <span className="cc-ss-v text-slate-300 font-mono">{regionCount != null ? `${regionCount} regional + coordinator` : EM}</span>
              </div>
              <div className="cc-ss-row">
                <span className="cc-ss-k">LIVE LINK</span>
                <span className={`cc-ss-v font-semibold ${link.tone === 'ok' ? 'text-emerald-400' : link.tone === 'warn' ? 'text-amber-400' : 'text-slate-400'}`}>{link.tone === 'ok' ? 'ON' : link.tone === 'warn' ? 'CONNECTING' : 'OFF'}</span>
              </div>
              <div className="cc-ss-row">
                <span className="cc-ss-k">OPTIMIZER</span>
                <span className="cc-ss-v text-slate-300">GA + MILP · {runtimeSec != null ? `${(runtimeSec / 60).toFixed(1)} min` : EM}</span>
              </div>
              <div className="cc-ss-row">
                <span className="cc-ss-k">MARITIME</span>
                <span className="cc-ss-v text-slate-400">{maritimeOverview?.enabled ? 'LIVE' : 'DISABLED'}</span>
              </div>
              <div className="cc-ss-row">
                <span className="cc-ss-k">ITERATIONS</span>
                <span className="cc-ss-v text-slate-300">{iterationsResolved.length ? `${iterationsResolved.length} on disk` : EM}</span>
              </div>
            </div>
          </InstrumentPanel>
        </div>

        <div className="cc-top-row-decision">
          <InstrumentPanel
            title="Current Decision"
            right={
              <div style={{ display: 'inline-flex', gap: 6 }}>
                <button type="button" className="cmp-btn" aria-pressed={comparing} onClick={() => setComparing((v) => !v)}
                  title="Two iterations side by side, each against the 30-seed mean" disabled={iterationsResolved.length < 2}>Compare</button>
                <span className="cx-badge cx-badge--purple">ITER {viewIterNum != null ? pad2(viewIterNum) : EM}</span>
                <span className={`cx-badge ${inspecting ? 'cx-badge--amber' : 'cx-badge--cyan'}`}>{inspecting ? 'INSPECTING' : 'SELECTED'}</span>
              </div>
            }
          >
            <div className="cx-current-decision-hero">
              <div className="cd-iter">
                <span className="cd-iter-label">{inspecting ? 'INSPECTING ITERATION' : 'SELECTED ITERATION'}</span>
                <span className="cd-iter-num" style={{ color: inspecting ? 'var(--cx-amber)' : '#a855f7' }}>
                  iter {viewIterNum != null ? pad2(viewIterNum) : EM}
                </span>
              </div>
              <div className="cd-tile">
                <span className="lbl">WEEKLY P&amp;L <Provenance rows={provOf('weekly_profit', 'summary_metrics.weekly_profit')} /></span>
                <span className="v-row">
                  <span className={`v ${weeklyProfit != null && weeklyProfit < 0 ? 'text-red-400' : 'text-cyan-400'}`}><UnitValue text={fmtUsd(weeklyProfit)} /></span>
                  <Sparkline values={series('profit')} active={viewIdx} label="Weekly profit by iteration" />
                </span>
                <span className="sub">{useSummary && sm.revenue != null ? `REVENUE ${fmtUsd(sm.revenue)}` : `ITER ${viewIterNum != null ? pad2(viewIterNum) : EM}`}</span>
                <VsMean value={weeklyProfit} stat={bench?.profit} unit="usd" n={bench?.n} excluded={bench?.excluded} />
              </div>
              <div className="cd-tile">
                <span className="lbl" title="Served TEU / total weekly demand (demand-weighted)">COVERAGE <Provenance rows={provOf('global_demand_weighted_coverage', 'summary_metrics.coverage')} /></span>
                <span className="v-row">
                  <span className="v text-emerald-400"><UnitValue text={fmtPct(coverage)} /></span>
                  <Sparkline values={series('coverage')} active={viewIdx} label="Coverage by iteration" />
                </span>
                <span className="sub">{teuServed != null ? `${fmtNum(Math.round(teuServed))} TEU SERVED` : EM}</span>
                <VsMean value={coverage} stat={bench?.coverage} unit="pct" n={bench?.n} excluded={bench?.excluded} />
              </div>
              <div className="cd-tile">
                <span className="lbl">SERVICES <Provenance rows={[...provOf('services_deployed', 'selected_services.length')].map(([k, v]) => (k === 'Field' ? [k, viewServices.length ? `iteration_results[iter ${viewIterNum}].selected_services (count)` : v] : [k, v]))} /></span>
                <span className="v-row">
                  <span className="v text-slate-100">{servicesCount ?? EM}</span>
                  <Sparkline values={series('servicesDeployed')} active={viewIdx} label="Services by iteration" />
                </span>
                <span className="sub">IN ITER {viewIterNum != null ? pad2(viewIterNum) : EM}</span>
                <VsMean value={servicesCount} stat={bench?.services} unit="count" n={bench?.n} excluded={bench?.excluded} />
              </div>
              <div className="cd-tile">
                <span className="lbl" title="Weekly profit / weekly revenue">MARGIN <Provenance rows={provOf('profit_margin_pct', 'summary_metrics.weekly_profit / revenue')} /></span>
                <span className="v-row">
                  <span className="v text-slate-100"><UnitValue text={fmtPct(marginPct)} /></span>
                  <Sparkline values={series('marginPct')} active={viewIdx} label="Margin by iteration" />
                </span>
                <span className="sub">ON REVENUE</span>
                <VsMean value={marginPct} stat={bench?.marginPct} unit="pct" n={bench?.n} excluded={bench?.excluded} />
              </div>
            </div>

            <div className="cc-cd-secondary-grid">
              <div className="cc-cd-sub-row">
                <span className="k">TEU UNSERVED</span>
                <span className="v">{unservedTeu != null ? fmtNum(Math.round(unservedTeu)) : EM}</span>
                <span className="k">REGIONS</span>
                <span className="v">{regionCount ?? EM}</span>
              </div>
              <div className="cc-cd-sub-row">
                <span className="k" title="Coordinator convergence score of this iteration (0–1)">SCORE</span>
                <span className="v">{score != null ? score.toFixed(3) : EM}</span>
                <span className="k" title="Average of the regional coverages (not demand-weighted)">REGIONAL AVG COV</span>
                <span className="v">{fmtPct(viewIter?.regionalCoverage)}</span>
              </div>
              <div className="cc-cd-sub-row">
                <span className="k">RERUN REQUESTED</span>
                <span className="v">{viewIter?.rerun == null ? EM : viewIter.rerun ? 'yes' : 'no'}</span>
                <span className="k">SELECTION METHOD</span>
                <span className="v text-cyan-400 font-bold">{selectionMethod ? titleCase(selectionMethod) : EM}</span>
              </div>
            </div>
          </InstrumentPanel>
        </div>
      </div>

      {/* ══ MIDDLE ROW: NETWORK INTELLIGENCE + RIGHT RAIL ══ */}
      <div className="cc-map-row">
        <InstrumentPanel
          title="Network Intelligence — Global Maritime Route Map"
          right={`${regionCount ?? EM} REGIONS · ${servicesCount ?? EM} SERVICES · ITER ${viewIterNum != null ? pad2(viewIterNum) : EM}`}
          bodyPadding="flush"
        >
          <MapCanvas
            optimizationState={optState}
            selectedServices={viewServices}
            maritimeOverview={maritimeOverview}
            height={360}
            region={region}
            onRegionChange={setRegion}
          />
        </InstrumentPanel>

        <div className="cc-side-rail">
          <InstrumentPanel title="LLM Diagnostics" right={<span className="text-[12px] font-mono text-emerald-400 font-semibold">FROM RUN</span>}>
            <LlmDiagnosticsPanel
              llmAggregate={optState?.llm_runtime_aggregate}
              llmMetrics={optState?.llm_runtime_metrics}
            />
          </InstrumentPanel>

          <InstrumentPanel title="Maritime Layers" right={<span className="text-[12px] font-mono text-slate-400 uppercase">{maritimeOverview?.enabled ? 'ENABLED' : 'OFF'}</span>}>
            <div className="cx-compact-empty">
              {maritimeOverview?.enabled
                ? 'Weather, congestion and routing-impact layers are enabled. See Maritime Situation.'
                : 'Weather, congestion and routing impact are off for this run (MARITIME_INTELLIGENCE_ENABLED=0). The plan uses the dataset only.'}
            </div>
          </InstrumentPanel>
        </div>
      </div>

      {comparing && iterationsResolved.length > 1 && (
        <InstrumentPanel title="Compare Iterations" right={<span className="text-[12px] font-mono text-slate-400 uppercase">{bench ? `vs ${bench.n}-seed mean` : 'no benchmark for this dataset'}</span>}>
          <ComparePanel
            iterations={iterationsResolved}
            iterResults={rawIterResults}
            selectedIter={canonicalSel}
            bench={bench}
            runLabel={runLabel}
            onClose={() => setComparing(false)}
          />
        </InstrumentPanel>
      )}

      {/* ══ PLAN ECONOMICS: where the money goes, how the plan compares, which services and agents drive it ══ */}
      <div className="cc-viz-grid">
        <InstrumentPanel title="Revenue to Profit" right={<span className="text-[12px] font-mono text-slate-400 uppercase">{inspecting ? `SELECTED ITER ${canonicalSel != null ? pad2(canonicalSel) : EM}` : 'WEEKLY'}</span>}>
          <CostWaterfall exportBase={runLabel} revenue={num(sm.revenue)} lines={costLines.map(([k, v]) => [k, Number(v)])} profit={num(sm.weeklyProfit)} />
        </InstrumentPanel>
        <InstrumentPanel title="Profit vs Coverage" right={<span className="text-[12px] font-mono text-slate-400 uppercase">{bench ? `${bench.n} SEEDS · PARETO` : 'ITERATIONS'}</span>}>
          <ProfitCoverage
            exportBase={runLabel}
            seeds={bench?.seeds || []}
            iterations={iterationsResolved}
            selectedIter={viewIterNum}
            currentSeed={optState?.source?.run?.kind === 'benchmark' ? optState.source.run.seed : null}
            dataset={bench?.dataset}
          />
        </InstrumentPanel>
        <InstrumentPanel title="Profit by Service" right={<span className="text-[12px] font-mono text-slate-400 uppercase">ITER {viewIterNum != null ? pad2(viewIterNum) : EM} · $ / WEEK</span>}>
          <ServicePnl exportBase={runLabel} services={viewServices} />
        </InstrumentPanel>
        <InstrumentPanel title="Coverage by Agent" right={<span className="text-[12px] font-mono text-slate-400 uppercase">TARGET 70%</span>}>
          <AgentCoverage exportBase={runLabel} regions={viewRegions} target={70} />
        </InstrumentPanel>
      </div>

      {/* ══ BOTTOM ROW 1: OPTIMIZATION PROGRESS + SYSTEM ACTIVITY ══ */}
      <div className="cc-bottom-split-row">
        <div className="cc-opt-progress-panel">
          <InstrumentPanel
            title="Optimization Progress"
            right={<span className="text-[12px] font-mono text-slate-400 uppercase">{iterationsResolved.length} ITERATIONS · CLICK TO INSPECT</span>}
            bodyPadding="flush"
          >
            <div className="cc-opt-container">
              <div className="cc-iter-cards">
                {iterationsResolved.map((it) => {
                  const isView = viewIterNum === it.iter;
                  const isFinal = canonicalSel === it.iter;
                  const role = isFinal ? 'SELECTED' : it.iter === 0 ? 'BASELINE' : 'CANDIDATE';
                  return (
                    <button
                      key={it.iter}
                      type="button"
                      onClick={() => setUserSelectedIter(it.iter === canonicalSel ? null : it.iter)}
                      className={`cc-iter-card ${isView ? 'is-active-glow' : ''}`}
                      aria-pressed={isView}
                    >
                      <span className="iter-hdr">ITER {pad2(it.iter)}</span>
                      <span className={`iter-pnl ${it.profit != null && it.profit < 0 ? 'text-red-400' : 'text-slate-100'}`}>{fmtUsd(it.profit)}</span>
                      <span className="iter-sub">{fmtPct(it.coverage)} · {it.score != null ? it.score.toFixed(3) : EM}</span>
                      <span className={`iter-tag ${isFinal ? 'text-emerald-400' : 'text-slate-400'}`}>• {role}</span>
                    </button>
                  );
                })}
              </div>

              <div className="cc-sparks-container">
                {[
                  ['PROFIT', profitPts, '#00d4ff'],
                  ['COVERAGE', covPts, '#10b981'],
                  ['SCORE', scorePts, '#f59e0b'],
                ].map(([title, pts, color]) => (
                  <div className="cc-spark-col" key={title}>
                    <span className="spark-title">{title}</span>
                    <div className="spark-svg-box">
                      <svg viewBox="0 0 100 35" className="spark-svg" role="img" aria-label={`${title.toLowerCase()} by iteration`}>
                        <polyline fill="none" stroke={color} strokeWidth="2" points={pts.map((p) => `${p.x},${p.y}`).join(' ')} />
                        {pts.map((p, i) => (
                          <circle key={i} cx={p.x} cy={p.y} r={iterationsResolved[i]?.iter === canonicalSel ? 4 : 3} fill={color} />
                        ))}
                      </svg>
                    </div>
                    <div className="spark-axis">
                      {iterationsResolved.map((it) => <span key={it.iter}>{pad2(it.iter)}</span>)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </InstrumentPanel>
        </div>

        <div className="cc-sys-activity-panel">
          <InstrumentPanel
            title="System Activity"
            right={<span className="text-[12px] font-mono text-slate-400 uppercase">FROM THE RUN'S AUDIT TRAIL</span>}
            bodyPadding="flush"
          >
            <div className="cc-activity-table-wrap">
              <table className="cc-activity-table">
                <thead>
                  <tr>
                    <th>STEP</th>
                    <th>COMPONENT</th>
                    <th>EVENT</th>
                    <th>STATUS</th>
                  </tr>
                </thead>
                <tbody>
                  {iterationsResolved.map((it, idx) => {
                    const isFinal = canonicalSel === it.iter;
                    const status = isFinal ? 'SELECTED' : it.rerun ? 'RERUN' : 'DONE';
                    return (
                      <tr key={it.iter}>
                        <td className="time">{pad2(idx + 1)}</td>
                        <td><span className="tag-comp">ITER {it.iter}</span></td>
                        <td className="msg">profit {fmtUsd(it.profit)} · cov {fmtPct(it.coverage)} · score {it.score != null ? it.score.toFixed(3) : EM} · rerun {it.rerun == null ? EM : it.rerun ? 'requested' : 'not requested'}</td>
                        <td className={isFinal ? 'sev-ok' : it.rerun ? 'sev-warn' : 'sev-info'}>{status}</td>
                      </tr>
                    );
                  })}
                  <tr>
                    <td className="time">{pad2(iterationsResolved.length + 1)}</td>
                    <td><span className="tag-comp">SELECTION</span></td>
                    <td className="msg">{selectionMethod ? titleCase(selectionMethod) : 'Selection'}: iter {canonicalSel != null ? canonicalSel : EM}</td>
                    <td className={canonicalSel != null ? 'sev-ok' : 'sev-warn'}>{canonicalSel != null ? 'OK' : 'UNKNOWN'}</td>
                  </tr>
                  <tr>
                    <td className="time">{pad2(iterationsResolved.length + 2)}</td>
                    <td><span className="tag-comp">DECISION</span></td>
                    <td className="msg">Final plan: {(sm.selected_services || []).length || EM} services · weekly profit {fmtUsd(sm.weeklyProfit)}</td>
                    <td className="sev-ok">OK</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </InstrumentPanel>
        </div>
      </div>

      {/* ══ BOTTOM ROW 2: 4 EXECUTIVE CARDS ══ */}
      <div className="cc-exec-cards-row">
        <div className="cc-exec-card">
          <div className="exec-title">▪ EXPLANATION</div>
          <div className="exec-body">
            {verdict && <div className="text-emerald-400 font-bold mb-1">Coordinator verdict: {titleCase(verdict)}</div>}
            <div className="text-slate-300">
              {inspecting ? `Iter ${pad2(viewIterNum)}: ` : ''}profit margin {fmtPct(marginPct)} with {fmtPct(coverage)} demand coverage.
            </div>
          </div>
        </div>

        <div className="cc-exec-card">
          <div className="exec-title">▪ STRENGTHS</div>
          <div className="exec-body">
            <div className="mb-1 text-slate-300">• Weekly profit {fmtUsd(weeklyProfit)} across {servicesCount ?? EM} services ({fmtUsd(profitPerService)} per service per week).</div>
            {!inspecting && costLines.length > 0 && (
              <div className="text-slate-400">• Weekly cost {fmtUsd(totalCost)}: {costLines.map(([k, v]) => `${k} ${fmtUsd(v)}`).join(', ')}.</div>
            )}
          </div>
        </div>

        <div className="cc-exec-card">
          <div className="exec-title">▪ WEAKNESSES</div>
          <div className="exec-body">
            <div className="mb-1 text-slate-300">• {coverage != null ? (100 - Number(coverage)).toFixed(1) + '%' : EM} of demand ({unservedTeu != null ? fmtNum(Math.round(unservedTeu)) : EM} TEU/week) unserved.</div>
            {costPerService != null && <div className="text-slate-400">• Cost per service {fmtUsd(costPerService)} per week.</div>}
          </div>
        </div>

        <div className="cc-exec-card">
          <div className="exec-title">▪ PRIORITY ACTIONS</div>
          <div className="exec-body">
            {lowestCovRegion
              ? <div className="mb-1 text-slate-300">• Raise coverage for the {lowestCovRegion.name || lowestCovRegion.region} agent (currently {fmtPct(lowestCovRegion.coverage)}).</div>
              : <div className="mb-1 text-slate-400">• No regional breakdown in this run.</div>}
            <div className="text-slate-400">• Route capacity toward the {unservedTeu != null ? fmtNum(Math.round(unservedTeu)) : EM} TEU/week still unserved.</div>
          </div>
        </div>
      </div>

      <footer className="cc-provenance-footer" role="contentinfo" aria-label="Data source">
        <div className="prov-line-1">
          <span className="prov-item"><span className="k">SOURCE</span> <span className="v">{optState?.source?.url || 'pipeline_output.json'} (selected_services, iteration_selection, regional_results)</span></span>
          <span className="prov-item"><span className="k">RUN</span> <span className="v">{runLabel}</span></span>
          <span className="prov-item"><span className="k">RECORDS</span> <span className="v">{(sm.selected_services || []).length}</span></span>
        </div>
      </footer>
    </div>
  );
}
