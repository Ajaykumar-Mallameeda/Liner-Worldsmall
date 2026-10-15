/**
 * Runtime Adapter — single normalization layer for pipeline_output.json
 * and WebSocket payloads. Components consume normalized schema only.
 */

export const RUNTIME_TRUTH_URL = '/pipeline_output.json';

const REGION_COLORS = {
  asia: '#00d4ff',
  europe: '#7c3aed',
  americas: '#10b981',
  middle_east: '#f59e0b',
  africa: '#ef4444',
};

export function getRegionColor(regionId) {
  return REGION_COLORS[regionId] || '#00d4ff';
}

export function normalizeRegion(data) {
  if (!data) return {};
  return {
    region: data.region ?? null,
    agent: data.agent ?? null,
    profit: data.weekly_profit ?? data.profit ?? null,
    weekly_profit: data.weekly_profit ?? data.profit ?? null,
    annualProfit: data.annual_profit ?? data.annualProfit ?? null,
    coverage: data.coverage_percent ?? data.coverage ?? null,
    coverage_percent: data.coverage_percent ?? data.coverage ?? null,
    services: data.services_selected ?? data.services ?? null,
    services_selected: data.services_selected ?? data.selected ?? null,
    margin: data.profit_margin_pct ?? data.margin ?? null,
    hubs: data.hub_ports ?? data.hubs ?? [],
    generated: data.services_generated ?? data.generated ?? null,
    filtered: data.services_filtered ?? data.filtered ?? null,
    selected: data.services_selected ?? data.selected ?? null,
    operating_cost: data.operating_cost ?? null,
    cost: data.total_cost ?? data.cost ?? null,
    total_cost: data.total_cost ?? data.cost ?? null,
    uncovered: data.uncovered_teu ?? data.uncovered ?? null,
    fuelCost: data.fuel_cost ?? null,
    transship_cost: data.transship_cost ?? null,
    portCost: data.port_cost ?? null,
    strategy: data.strategy ?? null,
    explanation: data.explanation ?? null,
    status: data.status ?? null,
    demand: data.total_demand ?? data.weekly_demand ?? null,
    total_demand: data.total_demand ?? data.weekly_demand ?? null,
    weekly_demand: data.weekly_demand ?? data.total_demand ?? null,
    satisfiedDemand: data.satisfied_demand ?? null,
    satisfied_demand: data.satisfied_demand ?? null,
    unservedDemand: data.unserved_demand ?? null,
    unserved_demand: data.unserved_demand ?? null,
    profitPerService: data.profit_per_service ?? null,
    costPerService: data.cost_per_service ?? null,
    // ── Extended fields: all sourced directly from pipeline_output.json ──
    profit_margin_pct: data.profit_margin_pct ?? null,
    profit_per_service: data.profit_per_service ?? null,
    // Agent wall-clock runtime (full regional agent time, not GA-specific)
    elapsed_sec: data.elapsed_sec ?? null,
    // LLM actuation record emitted by the regional agent
    llm_actuation: data.llm_actuation ?? null,
    // Regional policy set by the coordinator for this region
    regional_policy: data.regional_policy ?? null,
    // Archetype mix params from the coordinator
    archetype_params: data.archetype_params ?? null,
    // Individual cost columns
    fuel_cost: data.fuel_cost ?? null,
    port_cost: data.port_cost ?? null,
    // Selected services array (kept as reference, not iterated in hot path)
    selected_services: data.selected_services ?? [],
  };
}

export function normalizeIteration(data) {
  if (!data) return {};
  const m    = data.metrics         || {};  // from iteration_results[].metrics
  const fb   = data.feedback        || {};  // from iteration_results[].feedback
  const cq   = data.candidate_quality || {}; // from iteration_results[].candidate_quality

  // Coverage: iteration_audit uses data.coverage; iteration_results uses feedback
  const coverage = data.coverage ?? fb.average_regional_coverage ?? m.average_regional_coverage ?? 0;
  const globalCoverage =
    data.global_coverage ?? data.globalCoverage ??
    fb.global_demand_weighted_coverage ?? m.global_demand_weighted_coverage ?? coverage;

  // Score: iteration_audit → convergence_score; iteration_results → feedback.convergence_score
  const score = data.convergence_score ?? fb.convergence_score ?? data.score ?? m.convergence_score ?? 0;

  // Coverage gap: iteration_audit → coverage_gap; iteration_results → feedback.coverage_gap
  const coverageGap = data.coverage_gap ?? fb.coverage_gap ?? null;

  // Rerun: iteration_audit → needs_rerun; iteration_results → feedback.needs_rerun
  const rerun  = data.needs_rerun  ?? fb.needs_rerun  ?? false;
  const reason = data.rerun_reason ?? fb.rerun_reason ?? '';

  // Services: candidate_quality.services_deployed is the real field in iteration_results
  const servicesDeployed =
    cq.services_deployed ?? data.services_deployed ?? m.services_deployed ??
    m.total_services ?? (data.selected_services ? data.selected_services.length : null);

  return {
    iter: data.iteration ?? data.iter ?? 0,
    status: data.status ?? null,
    profit: data.profit ?? data.weekly_profit ?? m.weekly_profit ?? m.total_profit ?? 0,
    annualProfit: data.annual_profit ?? m.annual_profit ?? null,
    coverage,
    globalCoverage,
    score,
    coverageGap,
    conflictSeverity: data.conflict_severity ?? fb.conflict_severity ?? 0,
    rerun,
    reason,
    atIterationCap: data.at_iteration_cap ?? fb.at_iteration_cap ?? false,
    lowCoverage: data.low_coverage ?? fb.low_coverage ?? false,
    lowProfit: data.low_profit ?? fb.low_profit ?? false,
    conflictCount: data.conflict_count ?? fb.conflict_count ?? cq.conflict_count ?? 0,
    weights_used: data.weights_used ?? null,
    // Next-iteration weight adjustments proposed by the coordinator
    weight_adjustments: fb.weight_adjustments ?? null,
    selected_as_final: data.selected_as_final ?? null,
    selected_services: data.selected_services || [],
    servicesDeployed,
    services_deployed: servicesDeployed,
    satisfiedDemand: cq.satisfied_demand ?? data.satisfied_demand ?? m.satisfied_demand ?? null,
    unservedDemand: cq.unserved_demand ?? data.unserved_demand ?? m.unserved_demand ?? null,
    negativeProfitRegions: cq.negative_profit_regions ?? null,
    constraintViolations: cq.constraint_violations ?? 0,
    operatingCost: data.operating_cost ?? m.operating_cost ?? null,
    totalCost: data.total_cost ?? m.total_cost ?? null,
    marginPct: data.profit_margin_pct ?? m.profit_margin_pct ?? null,
    profitGap: data.profit_gap ?? fb.profit_gap ?? null,
    // Consensus and decisions from this iteration — passed as raw for the GA page
    consensus_result: data.consensus_result ?? null,
    decision_output: data.decision_output ?? null,
    // Regional breakdown for this iteration
    regional_results: data.regional_results ?? [],
    // Resolution log from coordinator
    resolution_log: data.resolution_log ?? [],
  };
}

export function normalizeGlobal(runtime, prev = {}) {
  const sm = runtime.summary_metrics || {};
  const dm = runtime.decision_output || {};
  const ps = runtime.problem_stats || {};
  const m = runtime.metrics || {};
  const its = runtime.iteration_selection || {};
  const llmAgg = runtime.llm_runtime_aggregate || {};
  const llmMet = runtime.llm_runtime_metrics || {};

  // Extract satisfied & unserved demand dynamically
  const satisfiedDemand = sm.satisfied_demand ?? dm.global_metrics?.total_satisfied_demand ?? prev.satisfiedDemand ?? null;
  const unservedDemand = sm.unserved_demand ?? dm.global_metrics?.total_unserved_demand ?? prev.unserved ?? null;
  const computedWeeklyDemand = sm.total_weekly_demand ?? sm.total_demand ?? ps.weekly_demand ?? (
    (satisfiedDemand != null && unservedDemand != null)
      ? (Number(satisfiedDemand) + Number(unservedDemand))
      : (m.weeklyDemand ?? prev.weeklyDemand ?? null)
  );

  // Parse ports and lanes dynamically from problem_analysis text or summary/problem stats
  let dynamicPorts = sm.total_ports ?? ps.ports ?? prev.ports ?? null;
  let dynamicLanes = sm.total_lanes ?? ps.lanes ?? prev.lanes ?? null;
  if ((!dynamicPorts || !dynamicLanes) && typeof runtime.problem_analysis === 'string') {
    const pMatch = runtime.problem_analysis.match(/(\d+)\s+ports/i);
    const lMatch = runtime.problem_analysis.match(/(\d+)\s+lanes/i);
    if (pMatch && !dynamicPorts) dynamicPorts = parseInt(pMatch[1], 10);
    if (lMatch && !dynamicLanes) dynamicLanes = parseInt(lMatch[1], 10);
  }

  // Calculate real net profit margin dynamically from revenue and weekly profit
  const rev = sm.revenue ?? dm.global_metrics?.total_revenue ?? prev.revenue ?? null;
  const totCost = sm.total_cost ?? sm.cost ?? dm.global_metrics?.total_cost ?? null;
  // Economic headline figures: a missing value stays null (unavailable); it is never replaced by 0.
  const wkProfit = sm.weekly_profit ?? dm.global_metrics?.total_profit ?? m.weeklyProfit ?? prev.weeklyProfit ?? null;
  const computedMargin = (rev && rev > 0 && wkProfit != null)
    ? (wkProfit / rev * 100)
    : (sm.profit_margin ?? dm.global_metrics?.profit_margin_pct ?? (m.margin ?? prev.margin ?? null));

  return {
    weeklyProfit: wkProfit,
    annualProfit: sm.annual_profit ?? dm.global_metrics?.annual_profit ?? m.annualProfit ?? prev.annualProfit ?? null,
    coverage: sm.global_demand_weighted_coverage ?? sm.coverage ?? dm.global_metrics?.global_demand_weighted_coverage ?? m.coverage ?? prev.coverage ?? null,
    regionalCoverage: sm.average_regional_coverage ?? dm.global_metrics?.average_regional_coverage ?? sm.coverage ?? prev.regionalCoverage ?? null,
    totalServices: sm.total_services ?? dm.global_metrics?.total_services ?? m.totalServices ?? (runtime.selected_services ? runtime.selected_services.length : (runtime.all_selected_services ? runtime.all_selected_services.length : (prev.totalServices ?? 0))),
    operatingCost: sm.operating_cost ?? dm.global_metrics?.operating_cost ?? m.operatingCost ?? prev.operatingCost ?? null,
    runtime: sm.total_runtime ?? sm.runtime_seconds ?? m.runtime ?? prev.runtime ?? 0,
    unserved: unservedDemand ?? 0,
    margin: computedMargin,
    revenue: rev,
    fuelCost: sm.fuel_cost ?? dm.global_metrics?.fuel_cost ?? prev.fuelCost ?? null,
    portCost: sm.port_cost ?? dm.global_metrics?.port_cost ?? prev.portCost ?? null,
    transshipCost: sm.transship_cost ?? sm.transshipment_cost ?? dm.global_metrics?.transship_cost ?? prev.transshipCost ?? null,
    satisfiedDemand: satisfiedDemand,
    weeklyDemand: computedWeeklyDemand,
    convergence: dm.feedback?.convergence_score ?? m.convergenceScore ?? prev.convergence ?? 0,
    ports: dynamicPorts,
    lanes: dynamicLanes,
    services: sm.total_services ?? dm.global_metrics?.total_services ?? ps.services ?? prev.services ?? null,
    selected_services: runtime.selected_services ?? runtime.all_selected_services ?? m.selected_services ?? prev.selected_services ?? [],
    all_selected_services: runtime.all_selected_services ?? runtime.selected_services ?? prev.all_selected_services ?? [],
    decision_output: dm,
    test_scorecard: runtime.test_scorecard ?? prev.test_scorecard ?? {},
    llm_runtime_metrics: llmMet,
    llm_runtime_aggregate: llmAgg,
    iteration_selection: its,
    iteration_results: runtime.iteration_results || [],
    executive_summary: runtime.executive_summary ?? prev.executive_summary ?? '',
    status: runtime.status ?? (runtime.health_status?.status === 'healthy' ? 'complete' : null) ?? prev.status ?? 'complete',
    run_id: runtime.run_id ?? runtime.orchestrator_run_id ?? (runtime.iterations_run != null ? ('run-' + String(runtime.iterations_run).padStart(2, '0')) : null) ?? prev.run_id ?? null,
    selected_iteration: runtime.final_selected_iteration ?? its.selected_iteration ?? runtime.best_iteration ?? runtime.selected_iteration ?? prev.selected_iteration ?? 0,
    evaluated_at: runtime.evaluated_at ?? runtime.created_at ?? prev.evaluated_at ?? null,
    lastFetchedAt: Date.now(),
    // ── Additional fields for GA/MILP page ───────────────────────────────
    coverage_target: runtime.shared_context?.global_objectives?.coverage_target ?? null,
    max_iterations: runtime.shared_context?.global_objectives?.max_iterations ?? runtime.iterations_run ?? null,
    iterations_run: runtime.iterations_run ?? null,
    health_status: runtime.health_status ?? null,
    consensus_result: runtime.consensus_result ?? null,
    problem_analysis: runtime.problem_analysis ?? null,
    iteration_audit: runtime.iteration_audit ?? [],
  };
}

export function normalizeDecision(decisionOutput) {
  if (!decisionOutput) return {};
  return {
    global_metrics: decisionOutput.global_metrics ?? {},
    feedback: decisionOutput.feedback ?? {},
    evaluation: decisionOutput.evaluation ?? {},
    conflicts: decisionOutput.conflicts ?? [],
    resolution_log: decisionOutput.resolution_log ?? [],
    decisions: decisionOutput.decisions ?? [],
  };
}

export function regionIdFromBackend(r, index = 0) {
  return r.region
    ? r.region.toLowerCase().replace(/\s+/g, '_')
    : `region_${index}`;
}

export function regionDisplayName(regionId, fallback) {
  if (fallback) return fallback;
  if (regionId === 'middle_east') return 'Middle East';
  return regionId.charAt(0).toUpperCase() + regionId.slice(1);
}

export function normalizeRegionsFromArray(rawRegions) {
  const processed = {};
  rawRegions.forEach((r, index) => {
    const regionId = regionIdFromBackend(r, index);
    processed[regionId] = {
      ...normalizeRegion(r),
      id: regionId,
      name: regionDisplayName(regionId, r.name || r.region),
      color: getRegionColor(regionId),
      selected_services: r.selected_services || [],
    };
  });
  return processed;
}

export function normalizeRegionsFromObject(rawRegions) {
  const processed = {};
  Object.entries(rawRegions).forEach(([id, data]) => {
    processed[id] = {
      ...normalizeRegion(data),
      id,
      name: regionDisplayName(id, data.name),
      color: getRegionColor(id),
      selected_services: data.selected_services || [],
    };
  });
  return processed;
}

export function normalizeRegions(rawRegions) {
  if (Array.isArray(rawRegions)) {
    return normalizeRegionsFromArray(rawRegions);
  }
  if (rawRegions && typeof rawRegions === 'object') {
    return normalizeRegionsFromObject(rawRegions);
  }
  return {};
}

export function normalizeRuntime(runtime) {
  if (!runtime) {
    return { global: {}, regions: {}, iterations: [], corridors: [] };
  }

  // Extract iterations with fallback priority: iteration_results > iteration_audit > iterations
  const rawIters = runtime.iteration_results || runtime.iteration_audit || runtime.iterations || [];

  // Build per-iteration regional map: { 0: { asia: {...}, europe: {...} }, 1: {...}, 2: {...} }
  // Sourced from iteration_results[N].regional_results — the authoritative per-iter regional data.
  const iteration_regions_map = {};
  if (Array.isArray(runtime.iteration_results)) {
    runtime.iteration_results.forEach((iterResult) => {
      const iterNum = iterResult.iteration ?? iterResult.iter ?? 0;
      const rawRegionalArr = iterResult.regional_results || [];
      iteration_regions_map[iterNum] = normalizeRegions(rawRegionalArr);
    });
  }

  // Scorecards from iteration_selection — global per-iter performance summary
  const scorecards = runtime.iteration_selection?.scorecards || [];

  return {
    global: normalizeGlobal(runtime),
    regions: normalizeRegions(runtime.regional_results || runtime.regions || {}),
    iterations: rawIters.map(normalizeIteration),
    corridors: runtime.corridors || [],
    iteration_results: runtime.iteration_results || [],
    iteration_selection: runtime.iteration_selection || {},
    iteration_regions_map,
    scorecards,
    llm_runtime_aggregate: runtime.llm_runtime_aggregate || {},
    llm_runtime_metrics: runtime.llm_runtime_metrics || {},
    raw: runtime,
  };
}

