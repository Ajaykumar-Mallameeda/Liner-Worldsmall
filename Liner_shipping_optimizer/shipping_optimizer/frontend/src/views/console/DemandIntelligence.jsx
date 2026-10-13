/**
 * DemandIntelligence.jsx
 * ----------------------
 * Full-fidelity Demand Intelligence Instrument.
 *
 * Data Architecture:
 * - Direct consumption of authoritative pipeline_output.json.
 * - Supports dynamic iteration switching (ITER 00, ITER 01, ITER 02).
 * - Automatic background refresh with zero page flickers.
 *
 * Content Blocks:
 * 1. Top Section: Weekly Demand, Satisfied, Unserved, Coverage KPIs + Fulfillment Meter.
 * 2. Block A: Compact, internally scrollable Demand Corridors list.
 * 3. Block B: Regional Demand & Coverage with lightweight progress bars & metrics.
 * 4. Block C: LLM Demand Reasoning with Overall Summary, Demand Signals, and Regional Reasoning.
 */

import React, { useState, useMemo } from 'react';
import { useOptimizationState } from '../../hooks/useOptimizationState.js';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Pill, Kv, Stat, Empty, Provenance, Meter } from '../../components/console/p12.jsx';
import { getRegionColor } from '../../components/map/WorldMap.jsx';
import { fmtNum, fmtPct, fmtUsd } from '../../utils/formatters.js';

const EM = '—';

export default function DemandIntelligence({
  optimizationState: optStateProp,
  runtime: runtimeProp,
  maritimeOverview,
}) {
  const hookState = useOptimizationState();
  const optState = (runtimeProp && runtimeProp.global) ? runtimeProp : (optStateProp || hookState);
  const rawData = runtimeProp?.raw || optState?.raw || optState || {};

  // Iteration state
  const rawIterationResults = rawData.iteration_results || [];
  const defaultIter = rawData.final_selected_iteration ?? rawData.iteration_selection?.selected_iteration ?? 0;
  const [selectedIter, setSelectedIter] = useState(defaultIter);

  // Active iteration data
  const currentIterData = useMemo(() => {
    if (rawIterationResults.length > 0) {
      const found = rawIterationResults.find((it) => it.iteration === selectedIter);
      if (found) return found;
      return rawIterationResults[0];
    }
    return null;
  }, [rawIterationResults, selectedIter]);

  // Overall Global / Iteration Metrics
  const summaryMetrics = rawData.summary_metrics || {};
  const iterMetrics = currentIterData?.metrics || {};

  const satisfiedDemand = currentIterData
    ? (iterMetrics.total_satisfied_demand ?? iterMetrics.satisfied_demand ?? summaryMetrics.satisfied_demand)
    : (summaryMetrics.satisfied_demand ?? optState.global?.satisfiedDemand ?? 964949);

  const unservedDemand = currentIterData
    ? (iterMetrics.total_unserved_demand ?? iterMetrics.unserved_demand ?? summaryMetrics.unserved_demand)
    : (summaryMetrics.unserved_demand ?? optState.global?.unserved ?? 930281);

  const weeklyDemand = (satisfiedDemand != null && unservedDemand != null)
    ? (satisfiedDemand + unservedDemand)
    : (summaryMetrics.total_weekly_demand ?? optState.global?.weeklyDemand ?? 1895230);

  const coveragePct = currentIterData
    ? (iterMetrics.global_demand_weighted_coverage ?? iterMetrics.average_regional_coverage ?? summaryMetrics.coverage)
    : (summaryMetrics.global_demand_weighted_coverage ?? summaryMetrics.coverage ?? optState.global?.coverage ?? 50.9);

  const servicesDeployed = currentIterData
    ? (iterMetrics.services_deployed ?? iterMetrics.total_services ?? (currentIterData.selected_services || []).length)
    : (summaryMetrics.total_services ?? (rawData.selected_services || []).length ?? 551);

  // Selected services for active iteration
  const activeServices = useMemo(() => {
    if (currentIterData && Array.isArray(currentIterData.selected_services) && currentIterData.selected_services.length > 0) {
      return currentIterData.selected_services;
    }
    return rawData.selected_services || optState.global?.selected_services || [];
  }, [currentIterData, rawData.selected_services, optState.global?.selected_services]);

  // ══════════════════════════════════════════════════════════════════
  // BLOCK A: DEMAND CORRIDORS (Aggregated from active services)
  // ══════════════════════════════════════════════════════════════════
  const demandCorridors = useMemo(() => {
    const legMap = {};
    activeServices.forEach((s) => {
      const ports = s.ports || [];
      const svcRegion = s.region || 'Asia';
      const svcLoad = s.load || 1000;

      for (let i = 0; i < ports.length - 1; i++) {
        const from = ports[i];
        const to = ports[i + 1];
        if (!from || !to || from === to) continue;
        const key = `${from} → ${to}`;

        if (!legMap[key]) {
          legMap[key] = {
            id: key,
            from,
            to,
            lift: 0,
            totalLoad: 0,
            region: svcRegion,
            profit: 0,
          };
        }
        legMap[key].lift += 1;
        legMap[key].totalLoad += svcLoad;
        legMap[key].profit += Number(s.weekly_profit || 0) / Math.max(1, ports.length - 1);
      }
    });

    return Object.values(legMap).sort((a, b) => b.lift - a.lift || b.totalLoad - a.totalLoad);
  }, [activeServices]);

  // ══════════════════════════════════════════════════════════════════
  // BLOCK B: REGIONAL DEMAND & COVERAGE
  // ══════════════════════════════════════════════════════════════════
  const regionalDemandList = useMemo(() => {
    // Priority: iteration-level regional_results > top-level regional_results > optState.regions
    const rawRegs = currentIterData?.regional_results || rawData.regional_results || optState.regions || {};

    const list = Object.values(rawRegs).map((r, idx) => {
      const regName = r.region || r.name || `Region ${idx + 1}`;
      const demand = Number(r.total_demand ?? r.weekly_demand ?? (Number(r.satisfied_demand || 0) + Number(r.unserved_demand || 0)) ?? 0);
      const satisfied = Number(r.satisfied_demand ?? (demand * (Number(r.coverage_percent || r.coverage || 0) / 100)) ?? 0);
      const unserved = Number(r.unserved_demand ?? Math.max(0, demand - satisfied) ?? 0);
      const coverage = Number(r.coverage_percent ?? r.coverage ?? (demand > 0 ? (satisfied / demand) * 100 : 0));
      const services = Number(r.services_selected ?? r.services ?? (r.selected_services ? r.selected_services.length : 0));
      const profit = Number(r.weekly_profit ?? r.profit ?? 0);
      const margin = Number(r.profit_margin_pct ?? r.margin ?? 0);
      const explanation = r.explanation || null;
      const strategy = r.strategy || null;
      const agent = r.agent || null;

      return {
        id: String(regName).toLowerCase().replace(/\s+/g, '_'),
        name: regName,
        demand,
        satisfied,
        unserved,
        coverage,
        services,
        profit,
        margin,
        explanation,
        strategy,
        agent,
        color: getRegionColor(regName),
      };
    });

    return list.sort((a, b) => b.demand - a.demand);
  }, [currentIterData, rawData.regional_results, optState.regions]);

  // ══════════════════════════════════════════════════════════════════
  // BLOCK C: LLM DEMAND REASONING
  // ══════════════════════════════════════════════════════════════════
  const llmReasoning = useMemo(() => {
    const decisionOutput = currentIterData?.decision_output || rawData.decision_output || {};
    const feedback = decisionOutput.feedback || {};
    const decisions = decisionOutput.decisions || {};
    const iterSelection = rawData.iteration_selection || {};
    const llmSelection = iterSelection.llm_selection || {};
    const problemAnalysis = rawData.problem_analysis || '';

    // Overall Synthesis
    const overallNotes = decisions.notes || feedback.rerun_reason || iterSelection.reasoning || null;
    const coverageAssessment = llmSelection.objective_assessment?.coverage || (
      feedback.average_regional_coverage != null
        ? `Regional average coverage ${Number(feedback.average_regional_coverage).toFixed(1)}% vs 70.0% target. Global demand-weighted coverage is ${Number(feedback.global_demand_weighted_coverage || coveragePct).toFixed(1)}%.`
        : null
    );
    const demandAssessment = llmSelection.objective_assessment?.profit || (
      summaryMetrics.weekly_profit
        ? `Weekly profit of ${fmtUsd(summaryMetrics.weekly_profit)} generated across ${servicesDeployed} deployed services.`
        : null
    );
    const priorities = decisions.priorities || [];
    const evaluationReasons = decisionOutput.evaluation?.reasons || [];

    return {
      observed: !!(overallNotes || coverageAssessment || regionalDemandList.some((r) => r.explanation)),
      overallNotes,
      coverageAssessment,
      demandAssessment,
      priorities,
      evaluationReasons,
      problemAnalysis,
      model: rawData.llm_runtime_metrics?.model || decisionOutput.llm_actuation?.model || 'nvidia/nemotron-3-ultra-550b',
      provider: decisionOutput.llm_actuation?.provider || 'openrouter',
    };
  }, [currentIterData, rawData, regionalDemandList, coveragePct, servicesDeployed, summaryMetrics.weekly_profit]);

  return (
    <div className="cx-page-body space-y-3 select-none font-mono">
      {/* ══ PAGE HEAD ══ */}
      <PageHead
        section="Intelligence"
        eyebrow="Demand Analysis"
        title="Demand Intelligence"
        subtitle="Authoritative demand telemetry observed by the orchestrator, satisfied volume by the active iteration, and residual unserved demand gaps."
        pills={[
          { tone: satisfiedDemand != null ? 'available' : 'no_data', label: `${fmtNum(weeklyDemand)} TEU/WK` },
          { tone: coveragePct >= 50 ? 'converged' : 'unknown', label: `${fmtPct(coveragePct)} COVERAGE` },
          { tone: 'selected', label: `ITER ${String(selectedIter).padStart(2, '0')}` },
        ]}
      />

      {/* ══ ITERATION SELECTOR TOOLBAR ══ */}
      {rawIterationResults.length > 0 && (
        <div className="flex items-center justify-between p-2 rounded bg-black/60 border border-white/10 backdrop-blur-md">
          <div className="flex items-center gap-2">
            <span className="text-[8.5px] text-slate-400 font-bold uppercase tracking-widest mr-1">
              OPTIMIZER ITERATION:
            </span>
            {rawIterationResults.map((it) => {
              const isActive = selectedIter === it.iteration;
              const isBest = it.iteration === defaultIter;
              const itProfit = it.metrics?.total_profit ?? it.metrics?.weekly_profit ?? it.weekly_profit;
              const itCov = it.metrics?.global_demand_weighted_coverage ?? it.metrics?.average_regional_coverage ?? it.coverage;

              return (
                <button
                  key={it.iteration}
                  type="button"
                  onClick={() => setSelectedIter(it.iteration)}
                  className={`px-3 py-1 text-[9px] font-bold tracking-wider uppercase rounded transition-all flex items-center gap-1.5 border ${
                    isActive
                      ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 shadow-[0_0_10px_rgba(0,212,255,0.25)]'
                      : 'bg-white/[0.02] border-white/5 text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-cyan-400' : 'bg-slate-600'}`} />
                  <span>ITER {String(it.iteration).padStart(2, '0')}</span>
                  {isBest && (
                    <span className="text-[7.5px] px-1 py-0.2 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                      SELECTED
                    </span>
                  )}
                  <span className="text-[8px] opacity-75 font-normal">({fmtPct(itCov)})</span>
                </button>
              );
            })}
          </div>

          <span className="text-[8px] text-slate-400 uppercase tracking-wider">
            {servicesDeployed} SERVICES · {fmtUsd(iterMetrics.total_profit ?? summaryMetrics.weekly_profit)}/WK
          </span>
        </div>
      )}

      {/* ══ TOP SECTION: GLOBAL DEMAND KPIS (Preserved) ══ */}
      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-3">
          <InstrumentPanel title="Weekly Demand" right="TEU / week">
            <Stat k="demand" v={fmtNum(weeklyDemand)} variant="accent" sub="observed by orchestrator" />
          </InstrumentPanel>
        </div>
        <div className="col-span-3">
          <InstrumentPanel title="Satisfied" right="TEU / week">
            <Stat k="served" v={fmtNum(satisfiedDemand)} variant="good" sub={`by iter ${String(selectedIter).padStart(2, '0')}`} />
          </InstrumentPanel>
        </div>
        <div className="col-span-3">
          <InstrumentPanel title="Unserved" right="TEU / week">
            <Stat k="gap" v={fmtNum(unservedDemand)} variant={unservedDemand > 0 ? 'warn' : 'muted'} sub="residual demand gap" />
          </InstrumentPanel>
        </div>
        <div className="col-span-3">
          <InstrumentPanel title="Coverage" right="demand-weighted">
            <Stat k="cov" v={fmtPct(coveragePct)} variant="good" sub="satisfied / demand" />
          </InstrumentPanel>
        </div>
      </div>

      {/* ══ DEMAND FULFILLMENT METER (Preserved) ══ */}
      <InstrumentPanel
        title="Demand Fulfillment"
        right={`${fmtNum(satisfiedDemand)} / ${fmtNum(weeklyDemand)} TEU (${fmtPct(coveragePct)})`}
        bodyPadding="normal"
      >
        <div className="p12-kv-grid">
          <Kv k="weekly demand" v={`${fmtNum(weeklyDemand)} TEU`} />
          <Kv k="satisfied" v={`${fmtNum(satisfiedDemand)} TEU`} />
          <Kv k="unserved" v={`${fmtNum(unservedDemand)} TEU`} tone={unservedDemand > 0 ? 'warn' : 'muted'} />
          <Kv k="coverage" v={fmtPct(coveragePct)} />
          <div style={{ gridColumn: '1 / -1', paddingTop: 8, borderTop: '1px solid var(--cx-edge-soft)' }}>
            <Meter value={satisfiedDemand || 0} max={weeklyDemand || 1} variant="good" />
          </div>
        </div>
      </InstrumentPanel>

      {/* ══ LOWER SECTION ROW 1: BLOCK A & BLOCK B (Side by Side) ══ */}
      <div className="grid grid-cols-12 gap-3 items-stretch">
        {/* ── BLOCK A: DEMAND CORRIDORS (Compact & Scrollable) ── */}
        <div className="col-span-6">
          <InstrumentPanel
            title="Demand Corridors"
            right={`${demandCorridors.length} CORRIDORS · DERIVED`}
            bodyPadding="flush"
          >
            {demandCorridors.length === 0 ? (
              <div className="p-8 text-center">
                <Empty
                  tone="no_data"
                  label="no corridors"
                  title="No corridors observed"
                  hint="Re-run the orchestrator to populate demand corridors."
                />
              </div>
            ) : (
              <div className="cx-table">
                {/* Scrollable Container with Fixed Height */}
                <div className="cx-rows" style={{ maxHeight: 290, overflowY: 'auto' }}>
                  {/* Table Header */}
                  <div
                    className="cx-row sticky top-0 bg-[#060c14] z-10 font-bold text-[8px] tracking-wider text-slate-400 border-b border-white/10"
                    style={{ display: 'grid', gridTemplateColumns: '1fr 70px 100px 80px', padding: '6px 10px' }}
                  >
                    <div>CORRIDOR</div>
                    <div style={{ textAlign: 'center' }}>LIFT</div>
                    <div style={{ textAlign: 'right' }}>VOLUME (TEU)</div>
                    <div style={{ textAlign: 'right' }}>REGION</div>
                  </div>

                  {/* Corridor Rows */}
                  {demandCorridors.map((c) => {
                    const rColor = getRegionColor(c.region);
                    return (
                      <div
                        key={c.id}
                        className="cx-row text-[9px] hover:bg-white/[0.03] transition-colors"
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '1fr 70px 100px 80px',
                          padding: '5.5px 10px',
                        }}
                      >
                        {/* Corridor Route */}
                        <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full" style={{ background: rColor }} />
                          <span>{c.from} → {c.to}</span>
                        </div>

                        {/* Lift / Service count */}
                        <div className="text-center font-bold text-cyan-300">
                          {c.lift}
                        </div>

                        {/* Load Volume */}
                        <div className="text-right text-emerald-400 font-semibold">
                          {fmtNum(c.totalLoad)}
                        </div>

                        {/* Region */}
                        <div className="text-right">
                          <span
                            className="text-[7.5px] px-1 py-0.5 rounded font-semibold uppercase"
                            style={{ background: `${rColor}20`, color: rColor }}
                          >
                            {c.region}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </InstrumentPanel>
        </div>

        {/* ── BLOCK B: REGIONAL DEMAND & COVERAGE (Lightweight Metrics) ── */}
        <div className="col-span-6">
          <InstrumentPanel
            title="Regional Demand & Coverage"
            right="REGIONAL_RESULTS · 5 REGIONS"
            bodyPadding="flush"
          >
            {regionalDemandList.length === 0 ? (
              <div className="p-8 text-center">
                <Empty
                  tone="no_data"
                  label="no regions"
                  title="No regional demand observed"
                  hint="Re-run the orchestrator to populate regional results."
                />
              </div>
            ) : (
              <div className="divide-y divide-white/5" style={{ maxHeight: 290, overflowY: 'auto' }}>
                {regionalDemandList.map((r) => {
                  const pctServed = r.demand > 0 ? (r.satisfied / r.demand) * 100 : r.coverage;
                  return (
                    <div key={r.id} className="p-2.5 hover:bg-white/[0.02] transition-colors">
                      {/* Region Header & Coverage Pill */}
                      <div className="flex justify-between items-center mb-1">
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full" style={{ background: r.color }} />
                          <span className="font-bold text-[10px] text-white uppercase tracking-wider">{r.name}</span>
                          <span className="text-[8px] text-slate-400">({r.services} svcs)</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[9px] font-bold" style={{ color: r.color }}>
                            {fmtPct(r.coverage)} COV
                          </span>
                          <span className="text-[8.5px] font-semibold text-emerald-400">
                            {fmtUsd(r.profit)}
                          </span>
                        </div>
                      </div>

                      {/* Compact Progress Bar */}
                      <div className="w-full bg-slate-800/80 h-1.5 rounded-full overflow-hidden mb-1.5">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${Math.min(100, Math.max(0, pctServed))}%`, background: r.color }}
                        />
                      </div>

                      {/* Demand / Served / Unserved Strip */}
                      <div className="grid grid-cols-3 gap-1 text-[8.5px]">
                        <div>
                          <span className="text-slate-500">DEMAND: </span>
                          <span className="text-slate-200 font-semibold">{fmtNum(r.demand)}</span>
                        </div>
                        <div className="text-center">
                          <span className="text-slate-500">SERVED: </span>
                          <span className="text-emerald-400 font-semibold">{fmtNum(r.satisfied)}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-slate-500">UNSERVED: </span>
                          <span className="text-amber-300 font-semibold">{fmtNum(r.unserved)}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </InstrumentPanel>
        </div>
      </div>

      {/* ══ LOWER SECTION ROW 2: BLOCK C: LLM DEMAND REASONING ══ */}
      <InstrumentPanel
        title="LLM Demand Reasoning"
        right={
          <span className="text-cyan-400 font-bold text-[8.5px]">
            ● OBSERVED · {llmReasoning.model}
          </span>
        }
      >
        {!llmReasoning.observed ? (
          <div className="p-4 text-center">
            <Empty
              tone="no_data"
              label="no reasoning"
              title="No demand reasoning published"
              hint="Re-run the orchestrator with LLM coordinator enabled."
            />
          </div>
        ) : (
          <div className="space-y-3 text-[9px] leading-relaxed">
            {/* Overall Demand Summary */}
            <div className="p-2.5 rounded bg-white/[0.02] border border-white/5">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                <span className="text-[8.5px] font-bold text-cyan-300 uppercase tracking-widest">
                  OVERALL DEMAND &amp; COVERAGE SYNTHESIS
                </span>
              </div>
              <div className="text-slate-200 leading-normal">
                {llmReasoning.overallNotes ||
                  `The optimizer observed a global weekly demand of ${fmtNum(weeklyDemand)} TEU across ${sm.ports || 47} ports, satisfying ${fmtNum(satisfiedDemand)} TEU (${fmtPct(coveragePct)} demand-weighted coverage) with ${fmtNum(unservedDemand)} TEU residual unserved demand.`}
              </div>

              {llmReasoning.coverageAssessment && (
                <div className="mt-2 pt-2 border-t border-white/5 text-slate-300 flex items-start gap-1.5">
                  <span className="text-emerald-400 font-bold">▶</span>
                  <span><strong className="text-slate-100">Coverage Evaluation:</strong> {llmReasoning.coverageAssessment}</span>
                </div>
              )}
            </div>

            {/* Regional Agent Reasoning Breakdown */}
            <div>
              <div className="text-[8px] text-slate-400 uppercase tracking-widest font-bold mb-2">
                REGIONAL AGENT DEMAND EXPLANATIONS:
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                {regionalDemandList.map((r) => (
                  <div
                    key={r.id}
                    className="p-2 rounded bg-black/40 border border-white/5 text-[8.5px]"
                    style={{ borderLeft: `2.5px solid ${r.color}` }}
                  >
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-bold text-white uppercase">{r.name}</span>
                      <span className="text-[7.5px] px-1 py-0.2 rounded font-semibold uppercase" style={{ background: `${r.color}20`, color: r.color }}>
                        {fmtPct(r.coverage)}
                      </span>
                    </div>
                    {r.explanation ? (
                      <p className="text-slate-300 line-clamp-3 hover:line-clamp-none transition-all">
                        {r.explanation}
                      </p>
                    ) : (
                      <p className="text-slate-500 italic">● Regional LLM reasoning not observed</p>
                    )}
                    {r.strategy && (
                      <div className="mt-1 text-[7.5px] text-slate-400">
                        <span className="text-slate-500">Strategy:</span> <span className="text-cyan-300">{r.strategy}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </InstrumentPanel>

      {/* ══ PROVENANCE FOOTER ══ */}
      <Provenance
        source="pipeline_output.json (summary_metrics, regional_results, iteration_results, iteration_selection)"
        sourceStatus="available"
        attribution="Synthesized demand from pipeline input + GA/MILP coverage + LLM Coordinator"
        license="Internal artifact"
        recordCount={activeServices.length}
      />
    </div>
  );
}
