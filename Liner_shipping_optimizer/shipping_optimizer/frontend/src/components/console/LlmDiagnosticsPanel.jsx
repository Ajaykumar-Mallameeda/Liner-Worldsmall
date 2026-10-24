/**
 * LlmDiagnosticsPanel.jsx
 * ------------------------
 * Operational runtime diagnostics panel for the LLM subsystem.
 * Accurately exposes runtime evidence from `llm_runtime_aggregate` and `llm_runtime_metrics`.
 *
 * Sourced dynamically from runtime truth without static hardcoded values.
 */

import React from 'react';

export default function LlmDiagnosticsPanel({ llmAggregate, llmMetrics }) {
  const agg = llmAggregate || {};
  const pt = agg.provider_telemetry || {};
  const cb = agg.component_breakdown || {};
  const lm = llmMetrics || {};
  const coord = agg.coordinator || {};
  const svcGen = agg.service_generator || {};
  const iterSel = agg.iteration_selector || {};
  const ledgerEntries = Object.values(agg.actuation_ledger || {});

  // 1. Coordinator:
  const coordEntries = ledgerEntries.filter(
    (e) => e.role === 'coordinator' || (e.component && e.component.startsWith('coordinator'))
  );
  const coordCalls = coordEntries.length > 0
    ? coordEntries.reduce((s, e) => s + (e.attempts || 1), 0)
    : (coord.coordinator_llm_attempts ?? cb.coordinator_ai_attempts ?? (lm.coordinator_llm_calls != null ? lm.coordinator_llm_calls : (coord.attempts ?? 0)));
  const coordAiSuccesses = coordEntries.length > 0
    ? coordEntries.filter((e) => e.ai_generated !== false && (e.successes || 0) > 0).length
    : (coord.coordinator_llm_successes ?? (lm.coordinator_ai_generated ? 1 : 0));
  const coordFallback = coordEntries.some((e) => e.fallback_uses > 0 || e.ai_generated === false) || coord.coordinator_fallback === true;
  const coordStatus = coordAiSuccesses > 0 ? 'ACTIVE' : (coordCalls > 0 ? (coordFallback ? 'FALLBACK' : 'POLICY') : 'IDLE');

  // 2. Regional Agents:
  const regionalEntries = ledgerEntries.filter(
    (e) => e.role === 'regional' || (e.component && e.component.startsWith('regional_'))
  );
  const regionalCalls = regionalEntries.length > 0
    ? regionalEntries.length
    : (lm.servicegen_regions ?? 0);
  const regionalAiSuccesses = regionalEntries.length > 0
    ? regionalEntries.filter((e) => e.ai_generated === true || (e.decision_source === 'llm' && (e.successes || 0) > 0)).length
    : (lm.servicegen_ai_count ?? 0);
  const regionalStatus = regionalCalls > 0
    ? (regionalAiSuccesses === regionalCalls
        ? 'ACTIVE'
        : (regionalAiSuccesses > 0 ? `ACTIVE (${regionalAiSuccesses}/${regionalCalls})` : 'FALLBACK'))
    : 'IDLE';

  // 3. Service Generator:
  const svcGenEntries = ledgerEntries.filter(
    (e) => e.role === 'service_generator' || (e.component && e.component.startsWith('service_generator'))
  );
  const svcGenCalls = svcGenEntries.length > 0
    ? svcGenEntries.reduce((s, e) => s + (e.attempts || 1), 0)
    : (svcGen.service_generator_ai_attempts ?? cb.service_generator_ai_attempts ?? (lm.servicegen_fallback_count != null ? 1 : 0));
  const svcGenAiSuccesses = svcGenEntries.length > 0
    ? svcGenEntries.filter((e) => e.ai_generated === true && (e.successes || 0) > 0).length
    : (svcGen.service_generator_ai_successes ?? 0);
  const svcGenFallback = svcGenEntries.some((e) => e.fallback_uses > 0 || (e.failures || 0) > 0 || e.ai_generated === false) || (svcGen.service_generator_fallbacks > 0);
  const svcGenStatus = svcGenAiSuccesses > 0 ? 'ACTIVE' : (svcGenCalls > 0 ? 'FALLBACK' : 'IDLE');

  // 4. Iteration Selector:
  const iterSelEntries = ledgerEntries.filter(
    (e) => e.role === 'iteration_selector' || (e.component && e.component.startsWith('iteration_selector'))
  );
  const iterSelCalls = iterSelEntries.length > 0
    ? iterSelEntries.reduce((s, e) => s + (e.attempts || 1), 0)
    : (iterSel.iteration_selector_llm_attempts ?? cb.iteration_selector_ai_attempts ?? 0);
  const iterSelAiSuccesses = iterSelEntries.length > 0
    ? iterSelEntries.filter((e) => e.ai_generated === true && (e.successes || 0) > 0).length
    : 0;
  const iterSelSource = iterSelEntries[0]?.decision_source || iterSel.selection_source || '';
  const iterSelStatus = iterSelAiSuccesses > 0
    ? 'ACTIVE'
    : (iterSelSource.includes('multi_objective') || iterSelSource.includes('rule') || iterSelSource.includes('deterministic') || iterSelSource.includes('policy')
        ? 'POLICY'
        : (iterSelCalls > 0 ? 'FALLBACK' : 'IDLE'));

  // 5. Headline totals:
  const computedTotalCalls = ledgerEntries.length > 0
    ? ledgerEntries.reduce((s, e) => s + (e.attempts || 1), 0)
    : (coordCalls + regionalCalls + svcGenCalls + iterSelCalls);

  const computedSuccesses = ledgerEntries.length > 0
    ? ledgerEntries.reduce((s, e) => s + (e.ai_generated !== false && (e.successes || 0) > 0 ? (e.successes || 1) : 0), 0)
    : (coordAiSuccesses + regionalAiSuccesses + svcGenAiSuccesses + iterSelAiSuccesses);

  const computedFallbacks = ledgerEntries.length > 0
    ? ledgerEntries.filter((e) => e.ai_generated === false || (e.failures || 0) > 0 || e.fallback_uses > 0).length
    : Math.max(0, computedTotalCalls - computedSuccesses);

  const totalCalls = computedTotalCalls;
  const successes = computedSuccesses;
  const fallbacks = computedFallbacks;
  const failures = pt.failures ?? 0;
  const cacheHits = pt.cache_hits ?? 0;

  const isLive = totalCalls != null && totalCalls > 0;
  const statusTone =
    !isLive ? 'NOT OBSERVED' :
    fallbacks > 0 && successes > 0 ? 'PARTIAL' :
    successes > 0 ? 'ACTIVE' :
    fallbacks > 0 ? 'FALLBACK' : 'IDLE';

  const statusColor =
    statusTone === 'ACTIVE' ? 'text-emerald-400' :
    statusTone === 'PARTIAL' ? 'text-cyan-400' :
    statusTone === 'FALLBACK' ? 'text-amber-400' :
    'text-slate-400';

  const providersCount = Array.isArray(agg.providers_used)
    ? agg.providers_used.length
    : (typeof agg.providers_used === 'number' ? agg.providers_used : Object.keys(pt.provider_call_counts || {}).length);

  const modelsCount = Array.isArray(agg.models_used)
    ? agg.models_used.length
    : (typeof agg.models_used === 'number' ? agg.models_used : Object.keys(pt.model_call_counts || {}).length);

  const actuationObservedCount = lm.llm_calls ?? (ledgerEntries.length > 0 ? ledgerEntries.length : computedTotalCalls);
  const actuationText = actuationObservedCount > 0 ? `OBSERVED · ${actuationObservedCount} CALLS` : 'NOT OBSERVED';

  return (
    <div className="p-2 font-mono text-[12px] leading-tight flex flex-col justify-between h-full select-none">
      {/* ── Status Header ── */}
      <div className="flex justify-between items-center pb-1.5 border-b border-white/5 mb-1.5">
        <span className="text-slate-400 uppercase tracking-widest text-[12px] font-semibold">LLM SUBSYSTEM</span>
        <span className={`font-bold text-[12px] uppercase tracking-wider ${statusColor}`}>
          ● {statusTone}
        </span>
      </div>

      {/* ── Headline Metrics ── */}
      <div className="grid grid-cols-3 gap-1 pb-1.5 border-b border-white/5 mb-1.5 text-center">
        <div className="bg-white/[0.02] p-1 border border-white/5">
          <div className="text-[12px] text-slate-400 uppercase tracking-wider">TOTAL CALLS</div>
          <div className="text-[12px] font-bold text-slate-100 mt-0.5">{totalCalls}</div>
        </div>
        <div className="bg-white/[0.02] p-1 border border-white/5">
          <div className="text-[12px] text-slate-400 uppercase tracking-wider">AI SUCCESS</div>
          <div className="text-[12px] font-bold text-emerald-400 mt-0.5">{successes}</div>
        </div>
        <div className="bg-white/[0.02] p-1 border border-white/5">
          <div className="text-[12px] text-slate-400 uppercase tracking-wider">FALLBACK</div>
          <div className="text-[12px] font-bold text-amber-400 mt-0.5">{fallbacks}</div>
        </div>
      </div>

      {/* ── Agent Breakdown ── */}
      <div className="space-y-1 pb-1.5 border-b border-white/5 mb-1.5 text-[12px]">
        <div className="flex justify-between items-baseline">
          <span className="text-slate-400">COORDINATOR</span>
          <span className="font-semibold text-slate-200">
            <span className="text-cyan-400 font-bold">{coordCalls}</span> {coordCalls === 1 ? 'call' : 'calls'} · <span className={coordStatus === 'ACTIVE' ? 'text-emerald-400' : 'text-amber-400'}>{coordStatus}</span>
          </span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-slate-400">REGIONAL AGENTS</span>
          <span className="font-semibold text-slate-200">
            <span className="text-cyan-400 font-bold">{regionalCalls}</span> {regionalCalls === 1 ? 'call' : 'calls'} · <span className="text-emerald-400">{regionalStatus}</span>
          </span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-slate-400">SERVICE GEN</span>
          <span className="font-semibold text-slate-200">
            <span className="text-cyan-400 font-bold">{svcGenCalls}</span> {svcGenCalls === 1 ? 'call' : 'calls'} · <span className={svcGenStatus === 'ACTIVE' ? 'text-emerald-400' : (svcGenStatus === 'FALLBACK' ? 'text-amber-400' : 'text-slate-400')}>{svcGenStatus}</span>
          </span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-slate-400">ITER SELECT</span>
          <span className="font-semibold text-slate-200">
            <span className="text-cyan-400 font-bold">{iterSelCalls}</span> {iterSelCalls === 1 ? 'call' : 'calls'} · <span className={iterSelStatus === 'ACTIVE' ? 'text-emerald-400' : (iterSelStatus === 'POLICY' ? 'text-purple-400' : 'text-amber-400')}>{iterSelStatus}</span>
          </span>
        </div>
      </div>

      {/* ── Providers & Cache Telemetry ── */}
      <div className="space-y-0.5 text-[12px]">
        <div className="flex justify-between items-baseline">
          <span className="text-slate-400">PROVIDERS / MODELS</span>
          <span className="font-semibold text-slate-300">{providersCount} / {modelsCount}</span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-slate-400">CACHE / RETRIES</span>
          <span className="font-semibold text-slate-300">
            {cacheHits} hits · <span className="text-amber-400">{failures} fail</span>
          </span>
        </div>
        <div className="flex justify-between items-baseline pt-0.5">
          <span className="text-slate-400">ACTUATION</span>
          <span className="font-semibold text-emerald-400 font-mono">{actuationText}</span>
        </div>
      </div>
    </div>
  );
}
