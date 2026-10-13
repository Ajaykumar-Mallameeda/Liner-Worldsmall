/**
 * RegionalAgents — Phase 12 COMPLETE
 * ====================================
 * Data source: pipeline_output.json via useOptimizationState
 *
 * Real fields used (verified against pipeline_output.json):
 *   regional_results[]:
 *     region, agent, status, services_generated, services_filtered,
 *     services_selected, weekly_profit, coverage_percent, total_demand,
 *     satisfied_demand, unserved_demand, profit_margin_pct, hub_ports,
 *     elapsed_sec, llm_actuation, regional_policy, archetype_params,
 *     operating_cost, total_cost, transship_cost, port_cost, fuel_cost
 *
 *   iteration_results[N].regional_results[] — same schema per iteration
 *   iteration_selection.scorecards[]        — global per-iter summary
 *   final_selected_iteration / best_iteration
 *   summary_metrics                         — global totals
 *   health_status.runtime_seconds           — global runtime
 *   llm_runtime_metrics                     — LLM call counts
 *
 * NOT OBSERVED (no fields exist in JSON):
 *   GA iterations (regional), GA best score (regional),
 *   GA runtime (regional), MILP status, MILP objective
 *
 * Polling: inherits 60-second poll from useOptimizationState (≤10 min target).
 */

import { useMemo, useState, useCallback, createElement, Fragment } from 'react';
import { useOptimizationState } from '../../hooks/useOptimizationState.js';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import {
  Pill, Kv, Stat, Empty, Tag, Dot, Provenance,
} from '../../components/console/p12.jsx';

const h = createElement;
const F = Fragment;

// ─── Formatting helpers ────────────────────────────────────────────────────
const EM = '—';
const NA = 'N/A';

function fmtNum(v, dec = 0) {
  if (v == null || v !== v) return EM; // NaN guard
  const n = Number(v);
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toFixed(dec);
}
function fmtUsd(v) {
  if (v == null) return EM;
  const n = Number(v);
  const neg = n < 0;
  const abs = Math.abs(n);
  let s;
  if (abs >= 1e9) s = '$' + (abs / 1e9).toFixed(2) + 'B';
  else if (abs >= 1e6) s = '$' + (abs / 1e6).toFixed(1) + 'M';
  else if (abs >= 1e3) s = '$' + (abs / 1e3).toFixed(0) + 'K';
  else s = '$' + Math.round(abs);
  return neg ? '-' + s : s;
}
function fmtPct(v, dec = 1) {
  if (v == null) return EM;
  return Number(v).toFixed(dec) + '%';
}
function fmtSec(v) {
  if (v == null) return EM;
  const s = Number(v);
  if (s >= 60) return (s / 60).toFixed(1) + ' min';
  return s.toFixed(1) + 's';
}
function fmtDelta(v, unit = '') {
  if (v == null) return EM;
  const n = Number(v);
  const sign = n >= 0 ? '+' : '';
  return sign + n.toFixed(1) + unit;
}
function fmtDeltaUsd(v) {
  if (v == null) return EM;
  const n = Number(v);
  const sign = n >= 0 ? '+' : '';
  if (Math.abs(n) >= 1e6) return sign + '$' + (n / 1e6).toFixed(1) + 'M';
  if (Math.abs(n) >= 1e3) return sign + '$' + (n / 1e3).toFixed(0) + 'K';
  return sign + '$' + Math.round(n);
}

// ─── Region colours (identical to existing colour system) ──────────────────
const REGION_COLORS = {
  asia: '#00d4ff',
  europe: '#7c3aed',
  americas: '#10b981',
  middle_east: '#f59e0b',
  africa: '#ef4444',
};
function regionColor(id) {
  return REGION_COLORS[String(id || '').toLowerCase().replace(/\s+/g, '_')] || '#94a3b8';
}

// ─── Tone helpers ──────────────────────────────────────────────────────────
function pnlTone(v) {
  if (v == null) return 'no_data';
  return Number(v) >= 0 ? 'available' : 'error';
}
function covTone(v) {
  if (v == null) return 'no_data';
  const n = Number(v);
  if (n >= 70) return 'available';
  if (n >= 50) return 'warn';
  return 'degraded';
}
function marginTone(v) {
  if (v == null) return 'no_data';
  const n = Number(v);
  if (n >= 15) return 'available';
  if (n >= 0) return 'warn';
  return 'error';
}
function iterTone(selected, pareto) {
  if (selected) return 'selected';
  if (pareto) return 'available';
  return 'no_data';
}

// ─── Micro UI primitives (local only) ─────────────────────────────────────
function Divider() {
  return h('div', {
    style: {
      height: 1,
      background: 'var(--cx-edge-soft)',
      margin: '8px 0',
    },
  });
}

function SectionLabel({ children }) {
  return h('div', {
    style: {
      fontFamily: 'var(--cx-mono)',
      fontSize: 9,
      color: 'var(--cx-text-faint)',
      textTransform: 'uppercase',
      letterSpacing: '0.14em',
      marginBottom: 6,
    },
  }, children);
}

function FilterBtn({ label, active, color, onClick }) {
  return h('button', {
    onClick,
    style: {
      fontFamily: 'var(--cx-mono)',
      fontSize: 10,
      padding: '3px 10px',
      background: active ? (color || 'var(--cx-accent)') : 'var(--cx-panel-bg)',
      border: active
        ? `1px solid ${color || 'var(--cx-accent)'}`
        : '1px solid var(--cx-edge)',
      color: active ? '#0a0e1a' : 'var(--cx-text)',
      cursor: 'pointer',
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
      transition: 'all 0.15s ease',
      fontWeight: active ? '700' : '400',
    },
  }, label);
}

function IterBtn({ iterNum, selected, pareto, score, onSelect }) {
  const isSelected = selected === iterNum;
  const accent = isSelected ? 'var(--cx-accent)' : (pareto ? '#10b981' : 'var(--cx-edge)');
  return h('button', {
    onClick: () => onSelect(iterNum),
    title: `Score: ${score != null ? score.toFixed(3) : 'N/A'} | ${pareto ? 'Pareto-optimal' : 'Dominated'}`,
    style: {
      fontFamily: 'var(--cx-mono)',
      fontSize: 10,
      padding: '3px 10px',
      background: isSelected ? accent : 'var(--cx-panel-bg)',
      border: `1px solid ${accent}`,
      color: isSelected ? '#0a0e1a' : 'var(--cx-text)',
      cursor: 'pointer',
      letterSpacing: '0.06em',
      transition: 'all 0.15s ease',
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
    },
  },
    h('span', null, `ITER ${String(iterNum).padStart(2, '0')}`),
    isSelected && h('span', {
      style: { fontSize: 8, opacity: 0.8 },
    }, ' ★'),
  );
}

function FunnelBar({ label, value, total, color }) {
  const pct = total > 0 ? Math.min(100, (value / total) * 100) : 0;
  return h('div', { style: { marginBottom: 4 } },
    h('div', {
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        fontFamily: 'var(--cx-mono)',
        fontSize: 9,
        color: 'var(--cx-text-faint)',
        marginBottom: 2,
      },
    },
      h('span', null, label),
      h('span', { style: { color: 'var(--cx-text)' } }, fmtNum(value)),
    ),
    h('div', {
      style: {
        height: 3,
        background: 'var(--cx-edge-soft)',
        position: 'relative',
        overflow: 'hidden',
      },
    },
      h('div', {
        style: {
          position: 'absolute',
          left: 0,
          top: 0,
          height: '100%',
          width: pct + '%',
          background: color || 'var(--cx-accent)',
          transition: 'width 0.3s ease',
        },
      }),
    ),
  );
}

function DeltaRow({ label, value, unit, style: extraStyle }) {
  if (value == null) return null;
  const n = Number(value);
  const positive = n >= 0;
  return h('div', {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      fontFamily: 'var(--cx-mono)',
      fontSize: 10,
      padding: '2px 0',
      ...extraStyle,
    },
  },
    h('span', { style: { color: 'var(--cx-text-faint)' } }, label),
    h('span', {
      style: { color: positive ? '#10b981' : '#ef4444', fontWeight: 600 },
    }, (unit === '$' ? fmtDeltaUsd(n) : fmtDelta(n, unit))),
  );
}

// ─── Main component ────────────────────────────────────────────────────────
export default function RegionalAgents(props) {
  const optStateProp = props && props.optimizationState;
  const hookState = useOptimizationState();
  const optState = optStateProp || hookState;

  const globalData   = optState.global || {};
  const baseRegions  = optState.regions || {};
  const iterRegMap   = optState.iteration_regions_map || {};
  const scorecards   = optState.scorecards || [];
  const iterSel      = optState.iteration_selection || {};
  const llmMetrics   = optState.llm_runtime_metrics || {};

  // Selected iteration from pipeline (the optimizer's winning choice)
  const pipelineSelectedIter = globalData.selected_iteration ?? 0;

  // User's currently viewed iteration (starts at pipeline-selected)
  const [viewIter, setViewIter] = useState(null);
  const activeIter = viewIter != null ? viewIter : pipelineSelectedIter;

  // Active region filter
  const [regionFilter, setRegionFilter] = useState('all');

  // The regions for the active iteration: use iteration_regions_map if available,
  // else fall back to the top-level regional_results (which is the selected iter)
  const activeRegions = useMemo(() => {
    if (Object.keys(iterRegMap).length > 0 && iterRegMap[activeIter] != null) {
      return iterRegMap[activeIter];
    }
    // Fallback: top-level regions (always the selected iteration's data)
    return baseRegions;
  }, [activeIter, iterRegMap, baseRegions]);

  const regionList = useMemo(() => Object.entries(activeRegions), [activeRegions]);

  // Filtered region list
  const visibleRegions = useMemo(() => {
    if (regionFilter === 'all') return regionList;
    return regionList.filter(([id]) =>
      id.toLowerCase().replace(/\s+/g, '_') === regionFilter
    );
  }, [regionList, regionFilter]);

  // Global summaries (always from the active iteration's region list)
  const totalServices = useMemo(() =>
    regionList.reduce((a, [, r]) => a + (Number(r.services_selected) || 0), 0),
    [regionList]
  );
  const totalProfit = useMemo(() =>
    regionList.reduce((a, [, r]) => a + (Number(r.weekly_profit) || 0), 0),
    [regionList]
  );
  const globalCoverage = globalData.coverage;

  // Iteration counts
  const iterCount = useMemo(() => {
    if (scorecards.length > 0) return scorecards.length;
    return Object.keys(iterRegMap).length || 1;
  }, [scorecards, iterRegMap]);

  const paretoIters = useMemo(() =>
    new Set((iterSel.pareto_optimal_iterations || []).map(Number)),
    [iterSel]
  );
  const candidateIters = useMemo(() =>
    new Set((iterSel.candidate_iterations || []).map(Number)),
    [iterSel]
  );

  // Previous iteration for delta comparison
  const prevIter = activeIter > 0 ? activeIter - 1 : null;
  const prevRegions = prevIter != null ? (iterRegMap[prevIter] || null) : null;

  // Scorecard for active and previous iterations
  const activeSC = useMemo(() =>
    scorecards.find(s => s.iteration === activeIter) || null,
    [scorecards, activeIter]
  );
  const prevSC = useMemo(() =>
    prevIter != null ? (scorecards.find(s => s.iteration === prevIter) || null) : null,
    [scorecards, prevIter]
  );

  // Global runtime from health_status
  const globalRuntimeSec = optState.raw?.health_status?.runtime_seconds ?? globalData.runtime ?? null;

  const overallTone = regionList.length > 0 ? 'available' : 'no_data';

  // ─── Handlers ──────────────────────────────────────────────────────────
  const handleIterSelect = useCallback((n) => {
    setViewIter(prev => prev === n ? null : n); // toggle off restores pipeline default
  }, []);

  // ─── Derived run info for footer ───────────────────────────────────────
  const runId = globalData.run_id || (optState.raw?.iterations_run != null
    ? 'run-' + String(optState.raw.iterations_run).padStart(2, '0')
    : NA);
  const evaluatedAt = globalData.evaluated_at || null;

  // ─── Render ────────────────────────────────────────────────────────────
  return h(F, null,
    h(PageHead, {
      section: 'AI Operations',
      eyebrow: 'Regional',
      title: 'Regional Agents',
      subtitle: 'Per-region orchestrator agents. Each block shows real optimizer evidence: filtering funnel, demand coverage, P&L, elapsed time, and LLM actuation. Data from pipeline_output.json.',
      pills: [
        { tone: overallTone, label: regionList.length + ' regions' },
        { tone: totalServices > 0 ? 'available' : 'no_data', label: fmtNum(totalServices) + ' services' },
        { tone: pnlTone(totalProfit), label: fmtUsd(totalProfit) + ' P&L' },
        { tone: 'active', label: 'ITER ' + String(activeIter).padStart(2, '0') + (activeIter === pipelineSelectedIter ? ' ★' : '') },
      ],
    }),

    h('div', { className: 'cx-page-body' },

      // ── Global summary row ──────────────────────────────────────────────
      h('div', { className: 'cx-grid-12', style: { marginBottom: 16 } },
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Regions', right: 'agents' },
            h(Stat, { k: 'regions', v: regionList.length, variant: 'accent', sub: 'world regions' })
          )
        ),
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Services', right: 'selected · iter ' + activeIter },
            h(Stat, { k: 'services', v: fmtNum(totalServices), sub: 'across all regions' })
          )
        ),
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Weekly P&L', right: '/ week' },
            h(Stat, {
              k: 'P&L',
              v: fmtUsd(totalProfit),
              variant: Number(totalProfit) >= 0 ? 'good' : 'warn',
              sub: 'per week · iter ' + activeIter,
            })
          )
        ),
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Global Coverage', right: 'demand-weighted' },
            h(Stat, {
              k: 'cov',
              v: globalCoverage != null ? fmtPct(globalCoverage) : EM,
              sub: 'global weighted average',
            })
          )
        ),
      ),

      // ── Filter & Iteration bar ──────────────────────────────────────────
      h('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 8,
          padding: '10px 0',
          marginBottom: 12,
          borderTop: '1px solid var(--cx-edge-soft)',
          borderBottom: '1px solid var(--cx-edge-soft)',
        },
      },
        // Region filter buttons
        h('div', { style: { display: 'flex', gap: 4, flexWrap: 'wrap' } },
          h(FilterBtn, {
            label: 'ALL', active: regionFilter === 'all',
            onClick: () => setRegionFilter('all'),
          }),
          ...Object.entries(REGION_COLORS).map(([id, color]) =>
            h(FilterBtn, {
              key: id,
              label: id.replace('_', ' ').toUpperCase(),
              active: regionFilter === id,
              color,
              onClick: () => setRegionFilter(regionFilter === id ? 'all' : id),
            })
          ),
        ),

        // Spacer
        h('div', { style: { flex: 1, minWidth: 12 } }),

        // Iteration selector
        h('div', { style: { display: 'flex', alignItems: 'center', gap: 4 } },
          h('span', {
            style: {
              fontFamily: 'var(--cx-mono)',
              fontSize: 9,
              color: 'var(--cx-text-faint)',
              textTransform: 'uppercase',
              letterSpacing: '0.12em',
              marginRight: 4,
            },
          }, 'Iteration:'),
          ...Array.from({ length: iterCount }, (_, i) => {
            const sc = scorecards.find(s => s.iteration === i);
            return h(IterBtn, {
              key: i,
              iterNum: i,
              selected: activeIter,
              pareto: paretoIters.has(i),
              score: sc?.convergence_score ?? null,
              onSelect: handleIterSelect,
            });
          }),
        ),
      ),

      // ── Regional cards grid ─────────────────────────────────────────────
      visibleRegions.length === 0
        ? h(Empty, {
            tone: 'no_data',
            label: 'no regions',
            title: 'No regional data',
            hint: 'Pipeline did not emit per-region data or no region matches filter.',
          })
        : h('div', { className: 'cx-grid-12', style: { marginBottom: 16 } },
            visibleRegions.map(([id, r]) => h(RegionalCard, {
              key: id + '-' + activeIter,
              id,
              r,
              activeIter,
              pipelineSelectedIter,
              color: regionColor(id),
            }))
          ),

      // ── Iteration comparison panel ──────────────────────────────────────
      h(IterationComparisonPanel, {
        activeIter,
        prevIter,
        activeSC,
        prevSC,
        activeRegions,
        prevRegions,
        pipelineSelectedIter,
        iterSel,
      }),

      // ── Source evidence footer ──────────────────────────────────────────
      h(Provenance, {
        source: 'pipeline_output.json · regional_results[] + iteration_results[]',
        sourceStatus: regionList.length > 0 ? 'available' : 'no_data',
        attribution: runId + ' · ITER ' + String(activeIter).padStart(2,'0') + (activeIter === pipelineSelectedIter ? ' SELECTED' : '') + ' · ' + regionList.length + ' regions · ' + iterCount + ' iters',
        license: 'Internal artifact',
        recordCount: regionList.length,
        snapshotId: evaluatedAt ? new Date(evaluatedAt).toLocaleTimeString() : undefined,
      }),
    ),
  );
}

// ─── Regional card ─────────────────────────────────────────────────────────
function RegionalCard({ id, r, activeIter, pipelineSelectedIter, color }) {
  const [expanded, setExpanded] = useState(false);

  const hubList = (r.hubs || r.hub_ports || []).slice(0, 6);
  const extraHubs = Math.max(0, (r.hubs || r.hub_ports || []).length - 6);

  // Filtering funnel — all three fields exist in the real JSON
  const generated = r.generated ?? r.services_generated ?? null;
  const filtered  = r.filtered  ?? r.services_filtered  ?? null;
  const selected  = r.selected  ?? r.services_selected  ?? r.services ?? null;
  const selRate   = (filtered > 0 && selected != null) ? (selected / filtered * 100) : null;
  const filtRate  = (generated > 0 && filtered != null) ? (filtered / generated * 100) : null;

  // LLM actuation — from regional_results[].llm_actuation
  const llm = r.llm_actuation || null;

  // Regional policy — from regional_results[].regional_policy
  const policy = r.regional_policy || null;

  // Margin tone
  const mTone = marginTone(r.profit_margin_pct ?? r.margin);

  return h('div', { className: 'cx-span-4' },
    h(InstrumentPanel, {
      title: r.name || r.region || id,
      right: h('span', {
        style: { display: 'inline-flex', gap: 6, alignItems: 'center' },
      },
        h('span', { style: { width: 8, height: 8, background: color, display: 'inline-block' } }),
        h('span', {
          style: {
            fontFamily: 'var(--cx-mono)',
            fontSize: 9,
            color: color,
            textTransform: 'uppercase',
            letterSpacing: '0.14em',
          },
        }, id.replace('_', ' ')),
        r.status && h('span', {
          style: {
            fontFamily: 'var(--cx-mono)',
            fontSize: 8,
            color: 'var(--cx-text-faint)',
            marginLeft: 4,
          },
        }, '· ' + String(r.status).toUpperCase()),
      ),
      bodyPadding: 'flush',
    },

      // ── Core metrics ──
      h('div', { className: 'p12-kv-grid', style: { padding: '10px 12px 6px' } },
        h(Kv, {
          k: 'P&L / week',
          v: fmtUsd(r.weekly_profit ?? r.profit),
          tone: pnlTone(r.weekly_profit ?? r.profit),
        }),
        h(Kv, {
          k: 'coverage',
          v: r.coverage_percent != null ? fmtPct(r.coverage_percent) : EM,
          tone: covTone(r.coverage_percent),
        }),
        h(Kv, {
          k: 'margin',
          v: r.profit_margin_pct != null ? fmtPct(r.profit_margin_pct) : EM,
          tone: mTone,
        }),
        h(Kv, { k: 'services', v: fmtNum(selected) }),
      ),

      // ── Demand block ──
      h('div', {
        style: {
          padding: '6px 12px',
          borderTop: '1px solid var(--cx-edge-soft)',
        },
      },
        h(SectionLabel, null, 'Demand'),
        h('div', { className: 'p12-kv-grid' },
          h(Kv, { k: 'total demand', v: r.total_demand != null ? fmtNum(r.total_demand) + ' TEU' : EM }),
          h(Kv, { k: 'served', v: r.satisfied_demand != null ? fmtNum(r.satisfied_demand) + ' TEU' : EM }),
          h(Kv, { k: 'unserved', v: r.unserved_demand != null ? fmtNum(r.unserved_demand) + ' TEU' : EM }),
        ),
      ),

      // ── Filtering funnel ──
      h('div', {
        style: {
          padding: '6px 12px',
          borderTop: '1px solid var(--cx-edge-soft)',
        },
      },
        h(SectionLabel, null, 'Optimization funnel'),
        generated != null && h(FunnelBar, {
          label: 'Generated',
          value: generated,
          total: generated,
          color: color,
        }),
        filtered != null && h(FunnelBar, {
          label: filtRate != null
            ? `Filtered (${fmtPct(filtRate, 0)} of gen)`
            : 'Filtered',
          value: filtered,
          total: generated,
          color: color,
        }),
        selected != null && h(FunnelBar, {
          label: selRate != null
            ? `Selected (${fmtPct(selRate, 0)} of filt)`
            : 'Selected',
          value: selected,
          total: generated,
          color: color,
        }),
      ),

      // ── Hub ports ──
      hubList.length > 0 && h('div', {
        style: {
          padding: '6px 12px',
          borderTop: '1px solid var(--cx-edge-soft)',
        },
      },
        h(SectionLabel, null, 'Hub ports'),
        h('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 4 } },
          hubList.map(p => h('span', {
            key: p,
            style: {
              fontFamily: 'var(--cx-mono)',
              fontSize: 10,
              padding: '2px 6px',
              background: 'var(--cx-panel-bg)',
              border: `1px solid ${color}44`,
              color: 'var(--cx-text)',
              letterSpacing: '0.04em',
            },
          }, p)),
          extraHubs > 0 && h('span', {
            style: {
              fontFamily: 'var(--cx-mono)',
              fontSize: 10,
              padding: '2px 6px',
              color: 'var(--cx-text-faint)',
            },
          }, '+' + extraHubs + ' more'),
        ),
      ),

      // ── Expand toggle ──
      h('button', {
        onClick: () => setExpanded(e => !e),
        style: {
          width: '100%',
          padding: '5px 12px',
          background: 'transparent',
          border: 'none',
          borderTop: '1px solid var(--cx-edge-soft)',
          color: 'var(--cx-text-faint)',
          fontFamily: 'var(--cx-mono)',
          fontSize: 9,
          textAlign: 'left',
          cursor: 'pointer',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
        },
      }, expanded ? '▲ collapse' : '▼ agent evidence'),

      // ── Expanded: runtime, LLM, policy, costs ──
      expanded && h('div', {
        style: {
          padding: '6px 12px 10px',
          borderTop: '1px solid var(--cx-edge-soft)',
          background: 'var(--cx-bg)',
        },
      },
        // Runtime
        h(SectionLabel, null, 'Agent runtime'),
        h('div', { className: 'p12-kv-grid', style: { marginBottom: 8 } },
          h(Kv, {
            k: 'elapsed',
            v: r.elapsed_sec != null ? fmtSec(r.elapsed_sec) : 'NOT OBSERVED',
          }),
          h(Kv, { k: 'GA runtime', v: 'NOT OBSERVED', tone: 'not_observed' }),
          h(Kv, { k: 'MILP status', v: 'NOT OBSERVED', tone: 'not_observed' }),
          h(Kv, { k: 'MILP objective', v: 'NOT OBSERVED', tone: 'not_observed' }),
        ),

        // LLM actuation
        h(SectionLabel, null, 'LLM actuation'),
        llm
          ? h('div', { className: 'p12-kv-grid', style: { marginBottom: 8 } },
              h(Kv, { k: 'ai generated', v: llm.ai_generated ? 'YES' : 'NO (fallback)', tone: llm.ai_generated ? 'active' : 'warn' }),
              h(Kv, { k: 'provider', v: llm.provider || NA }),
              h(Kv, { k: 'latency', v: llm.latency_sec != null ? fmtSec(llm.latency_sec) : NA }),
              h(Kv, { k: 'attempts', v: llm.attempts != null ? String(llm.attempts) : NA }),
              h(Kv, { k: 'successes', v: llm.successes != null ? String(llm.successes) : NA }),
              h(Kv, { k: 'fallbacks', v: llm.fallback_uses != null ? String(llm.fallback_uses) : NA }),
            )
          : h('div', {
              style: { fontFamily: 'var(--cx-mono)', fontSize: 9, color: 'var(--cx-text-faint)', marginBottom: 8 },
            }, 'NOT OBSERVED'),

        // Regional policy
        policy && h(F, null,
          h(SectionLabel, null, 'Regional policy'),
          h('div', { className: 'p12-kv-grid', style: { marginBottom: 8 } },
            h(Kv, { k: 'coverage priority', v: policy.coverage_priority != null ? fmtPct(policy.coverage_priority * 100, 0) : NA }),
            h(Kv, { k: 'profit priority', v: policy.profit_priority != null ? fmtPct(policy.profit_priority * 100, 0) : NA }),
            h(Kv, { k: 'vessel bias', v: policy.vessel_bias || NA }),
            h(Kv, { k: 'min margin', v: policy.min_service_margin != null ? fmtPct(policy.min_service_margin * 100, 0) : NA }),
          ),
        ),

        // Cost breakdown
        h(SectionLabel, null, 'Cost breakdown'),
        h('div', { className: 'p12-kv-grid' },
          h(Kv, { k: 'operating cost', v: fmtUsd(r.operating_cost) }),
          h(Kv, { k: 'total cost', v: fmtUsd(r.total_cost) }),
          h(Kv, { k: 'fuel cost', v: fmtUsd(r.fuel_cost ?? r.fuelCost) }),
          h(Kv, { k: 'port cost', v: fmtUsd(r.port_cost ?? r.portCost) }),
          h(Kv, { k: 'transship cost', v: fmtUsd(r.transship_cost) }),
          h(Kv, { k: 'profit / service', v: fmtUsd(r.profit_per_service ?? r.profitPerService) }),
        ),
      ),
    ),
  );
}

// ─── Iteration comparison panel ────────────────────────────────────────────
function IterationComparisonPanel({
  activeIter, prevIter, activeSC, prevSC,
  activeRegions, prevRegions,
  pipelineSelectedIter, iterSel,
}) {
  const hasComparison = activeSC != null;
  if (!hasComparison) return null;

  // Global deltas (from scorecards)
  const deltaCoverage = (prevSC && activeSC) ? activeSC.average_regional_coverage - prevSC.average_regional_coverage : null;
  const deltaProfit   = (prevSC && activeSC) ? activeSC.weekly_profit - prevSC.weekly_profit : null;
  const deltaServices = (prevSC && activeSC) ? activeSC.services_deployed - prevSC.services_deployed : null;
  const deltaScore    = (prevSC && activeSC) ? activeSC.convergence_score - prevSC.convergence_score : null;
  const deltaSatisfied= (prevSC && activeSC) ? activeSC.satisfied_demand - prevSC.satisfied_demand : null;

  return h('div', { style: { marginBottom: 16 } },
    h(InstrumentPanel, { title: 'Iteration Analysis', right: 'comparison + selection' },

      h('div', { className: 'cx-grid-12' },

        // ── Iteration scorecard table ──────────────────────────────────
        h('div', { className: 'cx-span-8' },
          h('div', { style: { padding: '8px 12px' } },
            h(SectionLabel, null, 'All iterations · scorecard'),
            h('div', {
              style: {
                display: 'grid',
                gridTemplateColumns: '70px repeat(5, 1fr)',
                gap: '2px 8px',
                fontFamily: 'var(--cx-mono)',
                fontSize: 9,
              },
            },
              // Header
              ...[
                'ITER', 'PROFIT', 'COVERAGE', 'SERVICES', 'SCORE', 'STATUS',
              ].map(h2 => h('span', {
                key: h2,
                style: { color: 'var(--cx-text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em', paddingBottom: 4, borderBottom: '1px solid var(--cx-edge-soft)' },
              }, h2)),
              // Rows
              ...(iterSel.scorecards || []).flatMap(sc => {
                const isActive = sc.iteration === activeIter;
                const isPipeline = sc.iteration === pipelineSelectedIter;
                const isPareto = sc.pareto_optimal;
                const tone = isActive ? '#00d4ff' : (isPipeline ? '#10b981' : (isPareto ? '#94a3b8' : 'var(--cx-text-faint)'));
                return [
                  h('span', { key: 'i'+sc.iteration, style: { color: tone, fontWeight: isActive ? 700 : 400 } },
                    'ITER ' + String(sc.iteration).padStart(2,'0') + (isPipeline ? ' ★' : '')
                  ),
                  h('span', { key: 'p'+sc.iteration, style: { color: isActive ? 'var(--cx-text)' : 'var(--cx-text-faint)' } }, fmtUsd(sc.weekly_profit)),
                  h('span', { key: 'c'+sc.iteration, style: { color: isActive ? 'var(--cx-text)' : 'var(--cx-text-faint)' } }, fmtPct(sc.average_regional_coverage)),
                  h('span', { key: 's'+sc.iteration, style: { color: isActive ? 'var(--cx-text)' : 'var(--cx-text-faint)' } }, fmtNum(sc.services_deployed)),
                  h('span', { key: 'sc'+sc.iteration, style: { color: isActive ? 'var(--cx-text)' : 'var(--cx-text-faint)' } }, sc.convergence_score?.toFixed(3) ?? EM),
                  h('span', { key: 'st'+sc.iteration, style: { color: isPareto ? '#10b981' : 'var(--cx-text-faint)' } },
                    isPareto ? 'PARETO' : 'DOMINATED'
                  ),
                ];
              }),
            ),
          ),
        ),

        // ── Delta column ──────────────────────────────────────────────
        h('div', { className: 'cx-span-4' },
          h('div', { style: { padding: '8px 12px' } },
            h(SectionLabel, null,
              prevIter != null
                ? `ITER ${String(activeIter).padStart(2,'0')} vs ITER ${String(prevIter).padStart(2,'0')}`
                : 'BASELINE ITERATION'
            ),
            prevSC && activeSC
              ? h('div', null,
                  h(DeltaRow, { label: 'Coverage', value: deltaCoverage, unit: ' pp' }),
                  h(DeltaRow, { label: 'Weekly P&L', value: deltaProfit, unit: '$' }),
                  h(DeltaRow, { label: 'Services', value: deltaServices, unit: '' }),
                  h(DeltaRow, { label: 'Score', value: deltaScore != null ? deltaScore * 1000 : null, unit: 'e-3' }),
                  h(DeltaRow, { label: 'Served TEU', value: deltaSatisfied, unit: ' TEU' }),
                )
              : h('div', {
                  style: { fontFamily: 'var(--cx-mono)', fontSize: 9, color: 'var(--cx-text-faint)' },
                }, 'Baseline — no previous iteration'),

            // Selection intelligence
            h(Divider, null),
            h(SectionLabel, null, 'Selection intelligence'),
            h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 9, lineHeight: 1.5 } },
              h('div', {
                style: { display: 'flex', justifyContent: 'space-between', marginBottom: 3 },
              },
                h('span', { style: { color: 'var(--cx-text-faint)' } }, 'METHOD'),
                h('span', { style: { color: 'var(--cx-text)', maxWidth: 120, textAlign: 'right' } },
                  (iterSel.selection_method || 'N/A').replace(/_/g, ' ').toUpperCase()
                ),
              ),
              h('div', {
                style: { display: 'flex', justifyContent: 'space-between', marginBottom: 3 },
              },
                h('span', { style: { color: 'var(--cx-text-faint)' } }, 'CONFIDENCE'),
                h('span', { style: { color: 'var(--cx-text)' } },
                  iterSel.confidence != null ? fmtPct(iterSel.confidence * 100) : EM
                ),
              ),
              h('div', {
                style: { display: 'flex', justifyContent: 'space-between' },
              },
                h('span', { style: { color: 'var(--cx-text-faint)' } }, 'PARETO ITERS'),
                h('span', { style: { color: '#10b981' } },
                  (iterSel.pareto_optimal_iterations || []).map(i => 'ITER ' + i).join(', ') || EM
                ),
              ),
            ),
          ),
        ),
      ),

      // ── Selection reasoning (truncated) ──────────────────────────────
      iterSel.reasoning && h('div', {
        style: {
          padding: '6px 12px 10px',
          borderTop: '1px solid var(--cx-edge-soft)',
          fontFamily: 'var(--cx-mono)',
          fontSize: 9,
          color: 'var(--cx-text-faint)',
          lineHeight: 1.6,
        },
      },
        h('span', { style: { color: 'var(--cx-text)', marginRight: 8 } }, 'SELECTION REASONING'),
        h('span', null, iterSel.reasoning.slice(0, 280) + (iterSel.reasoning.length > 280 ? '…' : '')),
      ),
    ),
  );
}
