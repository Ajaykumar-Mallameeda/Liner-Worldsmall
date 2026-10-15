/**
 * consoleSelectors.js
 * -------------------
 * Data extraction and projection helpers for the Command Center.
 * Dynamic selectors sourced directly from live optimization state.
 */

export function buildProfitSeries(iterations = []) {
  if (!iterations || iterations.length === 0) return [];
  return iterations.map((it) => (it.profit ? it.profit / 1e6 : (it.weeklyProfit ? it.weeklyProfit / 1e6 : 0)));
}

export function buildCoverageSeries(iterations = []) {
  if (!iterations || iterations.length === 0) return [];
  return iterations.map((it) => (it.coverage != null ? it.coverage : 0));
}

export function buildScoreSeries(iterations = []) {
  if (!iterations || iterations.length === 0) return [];
  return iterations.map((it) => (it.score != null ? it.score : 0));
}

export function getEffectiveSelectedIteration(optState, userSelIter) {
  const iterations = (optState && (optState.iterations || optState.global?.iterations)) || [];
  if (userSelIter != null) {
    const found = iterations.find((i) => i.iter === userSelIter || i.iteration === userSelIter);
    if (found) return { iteration: found, iterNum: userSelIter };
  }
  const globalSel = optState?.global?.selected_iteration ?? optState?.global?.iter ?? 0;
  const found = iterations.find((i) => i.iter === globalSel || i.iteration === globalSel);
  return {
    iteration: found || (iterations.length > 0 ? iterations[iterations.length - 1] : null),
    iterNum: globalSel,
  };
}

export function buildConsoleEvents(optState, maritimeOverview) {
  const iters = optState?.iterations || [];
  const gbl = optState?.global || {};
  const lm = optState?.llm_runtime_metrics || {};
  const agg = optState?.llm_runtime_aggregate || {};
  const events = [];

  iters.forEach((it, idx) => {
    const profitM = it.profit ? (it.profit / 1e6).toFixed(1) + 'M' : '0.0M';
    const cov = it.coverage != null ? Number(it.coverage).toFixed(2) + '%' : '0.00%';
    const sc = it.score != null ? Number(it.score).toFixed(3) : '0.000';
    const rerun = it.rerun ? 'rerun=yes' : 'rerun=no';
    events.push({
      id: `ev-it-${idx}`,
      ts: gbl.evaluated_at || new Date().toISOString(),
      source: `ITER ${it.iter ?? idx}`,
      type: 'iteration',
      severity: it.rerun ? 'warn' : 'info',
      summary: `profit $${profitM} · coverage ${cov} · score ${sc} · ${rerun}`,
    });
  });

  if (gbl.selected_iteration != null) {
    events.push({
      id: 'ev-sel',
      ts: gbl.evaluated_at || new Date().toISOString(),
      source: 'SELECTION',
      type: 'policy',
      severity: 'ok',
      summary: `Deterministic selection: iter ${gbl.selected_iteration} (policy)`,
    });
  }

  if (gbl.weeklyProfit != null || gbl.totalServices || (gbl.selected_services && gbl.selected_services.length > 0)) {
    const svcs = (gbl.selected_services && gbl.selected_services.length > 0) ? gbl.selected_services.length : (gbl.totalServices || 0);
    const profitText = gbl.weeklyProfit != null ? '$' + (gbl.weeklyProfit / 1e6).toFixed(1) + 'M' : 'unavailable';
    events.push({
      id: 'ev-dec',
      ts: gbl.evaluated_at || new Date().toISOString(),
      source: 'DECISION',
      type: 'decision',
      severity: 'ok',
      summary: `Final decision: ${svcs} services selected · weekly profit ${profitText}`,
    });
  }

  const observedLlmCalls = lm.llm_calls ?? (agg.total_calls ?? 0);
  if (observedLlmCalls > 0) {
    events.push({
      id: 'ev-llm',
      ts: gbl.evaluated_at || new Date().toISOString(),
      source: 'LLM',
      type: 'actuation',
      severity: 'info',
      summary: `LLM actuation · ${observedLlmCalls} calls observed`,
    });
  }

  return events;
}
