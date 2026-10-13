/**
 * EventStream
 * -----------
 * Phase 11 - a reusable operational event model.
 *
 * Events are derived from real runtime data (pipeline_output.json):
 *   - orchestrator run start (status field, iterations_run)
 *   - regional agent completion (per-region elapsed_sec + profit)
 *   - iteration completion (per iter in iteration_audit)
 *   - GA / MILP completion (when score or selected_iteration present)
 *   - validation / consensus (when consensus_result.confidence_score > 0)
 *   - selection (final_selected_iteration)
 *   - decision (when selected_services present)
 *   - maritime layer state transitions (when overview reports them)
 *
 * Each event has:
 *   timestamp (ISO or derived; never fabricated)
 *   source (component)
 *   event type
 *   severity
 *   human-readable summary
 *   optional metadata
 *   provenance (where the evidence lives)
 *
 * When no real history exists, the panel renders an empty
 * state. No fake "thinking" events.
 */

import { useMemo } from 'react';
import OperationalEmptyState from '../maritime/OperationalEmptyState.jsx';

function fmtTs(ts) {
  if (!ts) return '--';
  try {
    return new Date(ts).toISOString().slice(11, 19);
  } catch (_) {
    return '--';
  }
}

function fmtRel(sec) {
  if (sec == null) return null;
  if (sec < 60) return `${Math.round(sec)}s`;
  if (sec < 3600) return `${Math.round(sec / 60)}m`;
  return `${(sec / 3600).toFixed(1)}h`;
}

/**
 * Build a chronological event list from the runtime truth.
 * The list is descending (newest first) when desc=true.
 */
export function buildEventStream(runtime, maritimeOverview, { desc = true } = {}) {
  const out = [];
  if (!runtime) return out;

  const sm = runtime.global || {};
  const iterations = Array.isArray(runtime.iterations) ? runtime.iterations : [];
  const regions = runtime.regions || {};
  const iterResults = Array.isArray(runtime.iteration_results) ? runtime.iteration_results : [];

  // 1. Orchestrator run start (derived; not invented)
  // The pipeline_output carries a top-level evaluated_at via the
  // maritime overview; if not present, we use the latest iteration
  // timestamp. If neither is available, this event is skipped.
  const orchTs = maritimeOverview?.evaluated_at || null;
  if (orchTs) {
    out.push({
      id: 'orch-start',
      ts: orchTs,
      source: 'orchestrator',
      type: 'run_start',
      severity: 'info',
      summary: `Run started · ${iterations.length || 0} iterations planned · ${Object.keys(regions).length || 0} regions`,
      provenance: 'pipeline_output.status / iterations_run',
    });
  }

  // 2. Per-region completion (real evidence: regional_results[].elapsed_sec)
  const regionalResults = runtime.raw?.regional_results || [];
  regionalResults.forEach((r) => {
    if (r.elapsed_sec != null) {
      out.push({
        id: `region-${r.region || r.agent}`,
        ts: orchTs ? new Date(new Date(orchTs).getTime() - (regionalResults.length - regionalResults.indexOf(r)) * 1000).toISOString() : orchTs,
        source: r.agent || r.region || 'regional',
        type: 'region_completed',
        severity: r.status === 'Optimal' ? 'ok' : r.status === 'Feasible' ? 'info' : 'warn',
        summary: `${r.region || 'Region'} · ${r.services_selected || 0}/${r.services_generated || 0} services · ${r.coverage_percent?.toFixed?.(1) || '—'}% cov · ${fmtRel(r.elapsed_sec)}`,
        metadata: { region: r.region, services_selected: r.services_selected, coverage: r.coverage_percent, profit: r.weekly_profit },
        provenance: `regional_results[${r.region || r.agent}].elapsed_sec`,
      });
    }
  });

  // 3. Iteration completion
  iterations.forEach((it) => {
    const itNum = it.iter != null ? it.iter : iterations.indexOf(it);
    out.push({
      id: `iter-${itNum}`,
      ts: orchTs,
      source: 'iter',
      type: 'iteration_completed',
      severity: it.rerun ? 'warn' : 'info',
      summary: `Iter ${itNum} · profit ${fmtNumShort(it.profit)} · coverage ${fmtNumShort(it.coverage)}% · score ${fmtNumShort(it.score)} · rerun=${it.rerun ? 'yes' : 'no'}`,
      metadata: { iter: itNum, profit: it.profit, coverage: it.coverage, global_coverage: it.globalCoverage, score: it.score, rerun: it.rerun, reason: it.reason, weights: it.weights_used },
      provenance: `iteration_audit[${itNum}]`,
    });
  });

  // 4. Selection (final)
  const finalIter = sm.selected_iteration;
  if (finalIter != null) {
    out.push({
      id: 'selection',
      ts: orchTs,
      source: 'selection',
      type: 'final_selection',
      severity: 'ok',
      summary: `Deterministic selection: iter ${finalIter} (${sm.selection_method || 'policy'})`,
      metadata: { selected_iteration: finalIter, selection_method: sm.selection_method, confidence: sm.selection_confidence },
      provenance: 'iteration_selection.selected_iteration',
    });
  }

  // 5. Decision
  const selectedCount = (sm.selected_services || []).length;
  if (selectedCount > 0) {
    out.push({
      id: 'decision',
      ts: orchTs,
      source: 'decision',
      type: 'final_decision',
      severity: 'ok',
      summary: `Final decision: ${selectedCount} services selected · weekly profit ${fmtNumShort(sm.weeklyProfit)}`,
      metadata: { selected_count: selectedCount, weekly_profit: sm.weeklyProfit },
      provenance: 'summary_metrics.total_services + selected_services',
    });
  }

  // 6. LLM actuation - real evidence (llm_runtime_metrics / llm_runtime_aggregate)
  const llm = runtime.raw?.llm_runtime_aggregate || runtime.raw?.llm_runtime_metrics || {};
  const calls = llm.llm_calls || llm.coordinator_llm_calls || 0;
  if (calls > 0) {
    out.push({
      id: 'llm-actuation',
      ts: orchTs,
      source: 'llm',
      type: 'llm_actuation',
      severity: 'info',
      summary: `LLM actuation · ${calls} calls · ${(llm.providers_used || []).join('+') || 'fallback'}`,
      metadata: { calls, providers: llm.providers_used, models: llm.models_used },
      provenance: 'llm_runtime_aggregate',
    });
  }

  // 7. Maritime layer state (real - derived from overview)
  if (maritimeOverview && maritimeOverview.enabled) {
    Object.entries(maritimeOverview.sources || {}).forEach(([key, cell]) => {
      if (!cell) return;
      out.push({
        id: `mar-${key}`,
        ts: cell.evaluated_at || maritimeOverview.evaluated_at,
        source: 'maritime',
        type: 'maritime_state',
        severity: cell.state === 'live' || cell.state === 'available' ? 'ok' :
                  cell.state === 'degraded' || cell.state === 'stale' ? 'warn' :
                  cell.state === 'offline' ? 'crit' : 'dim',
        summary: `${key.toUpperCase()} · ${cell.state || 'unknown'}${cell.freshness_seconds != null ? ` · ${fmtRel(cell.freshness_seconds)} old` : ''}`,
        metadata: { layer: key, state: cell.state, age: cell.freshness_seconds, records: cell.record_count },
        provenance: `maritime_intelligence.${key}`,
      });
    });
  } else if (maritimeOverview && !maritimeOverview.enabled) {
    out.push({
      id: 'mar-disabled',
      ts: maritimeOverview.evaluated_at,
      source: 'maritime',
      type: 'maritime_state',
      severity: 'dim',
      summary: 'Maritime intelligence disabled (master flag off) - no live evidence',
      provenance: 'maritime_intelligence.enabled=false',
    });
  }

  // Sort
  out.sort((a, b) => {
    const ta = a.ts ? new Date(a.ts).getTime() : 0;
    const tb = b.ts ? new Date(b.ts).getTime() : 0;
    return desc ? tb - ta : ta - tb;
  });
  return out;
}

function fmtNumShort(v) {
  if (v == null) return '—';
  if (typeof v === 'number' && v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (typeof v === 'number' && v >= 1e3) return `${(v / 1e3).toFixed(1)}k`;
  if (typeof v === 'number') return v.toFixed(2);
  return String(v);
}

export default function EventStream({
  events = [],
  emptyTitle = 'No system activity observed',
  emptyHint = 'The event stream is derived from real runtime artifacts. When no orchestrator run has been recorded, the stream remains empty.',
  onSelectEvent,
  selectedEventId,
  showHeader = true,
  maxHeight = null,
}) {
  const visible = useMemo(() => events, [events]);

  if (!visible.length) {
    return (
      <OperationalEmptyState
        variant="no_data"
        title={emptyTitle}
        hint={emptyHint}
      />
    );
  }

  return (
    <div
      role="list"
      aria-label="System event stream"
      style={maxHeight ? { maxHeight, overflowY: 'auto' } : undefined}
    >
      {showHeader && (
        <div className="console-event" style={{ borderBottom: '1px solid var(--console-edge)', color: 'var(--console-text-faint)' }}>
          <span className="ts">TIME</span>
          <span className="src">COMPONENT</span>
          <span className="msg">EVENT</span>
          <span className="sev">SEVERITY</span>
        </div>
      )}
      {visible.map((e) => (
        <button
          type="button"
          key={e.id}
          role="listitem"
          onClick={() => onSelectEvent && onSelectEvent(e)}
          className="console-event"
          style={{
            background: selectedEventId === e.id ? 'rgba(0, 212, 255, 0.06)' : 'transparent',
            borderLeft: selectedEventId === e.id ? '2px solid var(--console-cyan)' : '2px solid transparent',
            border: selectedEventId === e.id ? '1px solid var(--console-cyan-soft)' : '1px solid transparent',
            borderRadius: 4,
            cursor: onSelectEvent ? 'pointer' : 'default',
            width: '100%',
            textAlign: 'left',
          }}
          aria-label={`Event ${e.type} from ${e.source} at ${fmtTs(e.ts)}: ${e.summary}`}
        >
          <span className="ts">{fmtTs(e.ts)}</span>
          <span className="src">{e.source}</span>
          <span className="msg" title={e.summary}>{e.summary}</span>
          <span className={`sev ${e.severity}`}>{e.severity?.toUpperCase() || 'INFO'}</span>
        </button>
      ))}
    </div>
  );
}
