/**
 * GaMilp — GA / MILP Optimization Console
 * =========================================
 * Focused strictly on: "GA / MILP optimization evidence + convergence analysis"
 *
 * Contains exactly the four primary convergence / evolution blocks:
 *   1. CONVERGENCE · SCORE (Audit Trail)
 *   2. COVERAGE EVOLUTION (% · Global Demand-Weighted)
 *   3. PROFIT EVOLUTION (USD / Week)
 *   4. SERVICES DEPLOYED (Count)
 *
 * All other detailed decision, iteration overview, weight evolution,
 * and filtering evidence have been relocated to Decision Centre.
 * Sourced directly from pipeline_output.json. No fabricated values.
 */

import { useMemo, createElement, Fragment } from 'react';
import { useOptimizationState } from '../../hooks/useOptimizationState.js';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Stat, Provenance } from '../../components/console/p12.jsx';
import { selectedIterationOf } from '../../runtime/consoleSelectors.js';
import GaPlayback from '../../components/charts/GaPlayback.jsx';

const h = createElement;
const F = Fragment;

// ─── Formatters ────────────────────────────────────────────────────────────
const EM = '—';

function fmtNum(v, dec = 0) {
  if (v == null || v !== v) return EM;
  const n = Number(v);
  if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K';
  return n.toFixed(dec);
}

function fmtUsd(v) {
  if (v == null) return EM;
  const n = Number(v);
  const neg = n < 0;
  const abs = Math.abs(n);
  let s = abs >= 1e9 ? '$' + (abs / 1e9).toFixed(2) + 'B'
        : abs >= 1e6 ? '$' + (abs / 1e6).toFixed(1) + 'M'
        : abs >= 1e3 ? '$' + (abs / 1e3).toFixed(0) + 'K'
        : '$' + Math.round(abs);
  return neg ? '-' + s : s;
}

function fmtPct(v, dec = 1) {
  return v == null ? EM : Number(v).toFixed(dec) + '%';
}

function fmtSec(v) {
  if (v == null) return EM;
  const s = Number(v);
  return s >= 3600 ? (s / 3600).toFixed(1) + ' hr'
       : s >= 60   ? (s / 60).toFixed(1) + ' min'
       : s.toFixed(1) + 's';
}

function fmtDelta(v, unit = '', dec = 1) {
  if (v == null) return EM;
  const n = Number(v);
  return (n >= 0 ? '+' : '') + n.toFixed(dec) + unit;
}

function fmtDeltaUsd(v) {
  if (v == null) return EM;
  const n = Number(v);
  const sign = n >= 0 ? '+' : '';
  const abs = Math.abs(n);
  return abs >= 1e9 ? sign + '$' + (n / 1e9).toFixed(2) + 'B'
       : abs >= 1e6 ? sign + '$' + (n / 1e6).toFixed(1) + 'M'
       : abs >= 1e3 ? sign + '$' + (n / 1e3).toFixed(0) + 'K'
       : sign + '$' + Math.round(n);
}

function deltaColor(v) {
  if (v == null) return 'var(--cx-text-faint)';
  return Number(v) >= 0 ? '#10b981' : '#ef4444';
}

// ─── Chart Palette (Rich contrast, readable & professional) ─────────────────
const CHART = {
  score:    { line: '#22d3ee', area: 'rgba(34,211,238,0.14)',  dot: '#22d3ee' },
  coverage: { line: '#34d399', area: 'rgba(52,211,153,0.12)',  dot: '#34d399' },
  profit:   { line: '#fbbf24', area: 'rgba(251,191,36,0.12)',  dot: '#fbbf24' },
  services: { line: '#a78bfa', area: 'rgba(167,139,250,0.12)', dot: '#a78bfa' },
};

// ─── Inline SVG Convergence Chart Component ─────────────────────────────────
function ConvergenceChart({ values, palette, height = 130, selectedIter = null, yFormat = v => v.toFixed(3) }) {
  if (!Array.isArray(values) || values.length === 0) {
    return h('div', {
      style: {
        height, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)',
      },
    }, 'NO DATA RECORDED');
  }

  const W = 500;
  const H = height;
  const PAD = { top: 14, right: 18, bottom: 22, left: 46 };
  const cW = W - PAD.left - PAD.right;
  const cH = H - PAD.top - PAD.bottom;

  const nums = values.map(Number).filter(Number.isFinite);
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const range = max === min ? 1 : max - min;
  const stepX = nums.length > 1 ? cW / (nums.length - 1) : cW / 2;

  const pts = nums.map((y, i) => ({
    x: PAD.left + (nums.length === 1 ? cW / 2 : i * stepX),
    y: PAD.top + cH - ((y - min) / range) * cH,
    val: y,
    i,
  }));

  const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const areaPath = `M ${PAD.left} ${PAD.top + cH} ` +
    pts.map(p => `L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ') +
    ` L ${(PAD.left + (nums.length > 1 ? (nums.length - 1) * stepX : cW / 2)).toFixed(1)} ${PAD.top + cH} Z`;

  const yTicks = [min, (min + max) / 2, max];
  const gradId = 'grad-' + palette.line.replace('#', '');

  return h('svg', {
    width: '100%',
    height: H,
    viewBox: `0 0 ${W} ${H}`,
    preserveAspectRatio: 'none',
    style: { display: 'block', overflow: 'visible' },
  },
    h('defs', null,
      h('linearGradient', { id: gradId, x1: '0', y1: '0', x2: '0', y2: '1' },
        h('stop', { offset: '0%', stopColor: palette.line, stopOpacity: 0.28 }),
        h('stop', { offset: '100%', stopColor: palette.line, stopOpacity: 0 }),
      ),
      h('filter', { id: 'glow-' + gradId, x: '-20%', y: '-20%', width: '140%', height: '140%' },
        h('feGaussianBlur', { in: 'SourceGraphic', stdDeviation: '1.5', result: 'blur' }),
        h('feMerge', null,
          h('feMergeNode', { in: 'blur' }),
          h('feMergeNode', { in: 'SourceGraphic' }),
        ),
      ),
    ),
    // Background Grid lines
    ...[0, 0.5, 1].map(t =>
      h('line', {
        key: 'gl' + t,
        x1: PAD.left, x2: PAD.left + cW,
        y1: PAD.top + (1 - t) * cH,
        y2: PAD.top + (1 - t) * cH,
        stroke: 'rgba(255,255,255,0.06)',
        strokeWidth: 1,
        strokeDasharray: t === 0 || t === 1 ? 'none' : '3,3',
      })
    ),
    // Area fill
    h('path', { d: areaPath, fill: `url(#${gradId})` }),
    // Line trace
    h('path', {
      d: linePath,
      fill: 'none',
      stroke: palette.line,
      strokeWidth: 1.8,
      strokeLinejoin: 'round',
      strokeLinecap: 'round',
      filter: `url(#glow-${gradId})`,
    }),
    // Data point circles
    pts.map(p => {
      const isSel = selectedIter != null && p.i === selectedIter;
      return h('circle', {
        key: p.i,
        cx: p.x, cy: p.y,
        r: isSel ? 5.5 : 3.5,
        fill: isSel ? palette.dot : '#0a0e1a',
        stroke: palette.dot,
        strokeWidth: isSel ? 2.5 : 1.5,
        filter: `url(#glow-${gradId})`,
      });
    }),
    // Data point value labels
    pts.map(p => {
      const above = p.y - PAD.top > 16;
      return h('text', {
        key: 'lbl' + p.i,
        x: p.x,
        y: above ? p.y - 7 : p.y + 14,
        textAnchor: 'middle',
        fontFamily: 'monospace',
        fontSize: 12,
        fill: palette.line,
        opacity: 0.95,
        fontWeight: 600,
      }, yFormat(p.val));
    }),
    // X-axis iteration labels
    pts.map(p =>
      h('text', {
        key: 'xi' + p.i,
        x: p.x,
        y: H - 4,
        textAnchor: 'middle',
        fontFamily: 'monospace',
        fontSize: 12,
        fill: 'rgba(255,255,255,0.4)',
      }, 'ITER ' + String(p.i).padStart(2, '0'))
    ),
    // Y-axis tick labels
    yTicks.map((tick, ti) => {
      const yPos = PAD.top + cH - ((tick - min) / range) * cH;
      return h('text', {
        key: 'yt' + ti,
        x: PAD.left - 4,
        y: yPos + 3,
        textAnchor: 'end',
        fontFamily: 'monospace',
        fontSize: 12,
        fill: 'rgba(255,255,255,0.35)',
      }, yFormat(tick));
    }),
  );
}

// ─── Analytical Block Card ──────────────────────────────────────────────────
function AnalyticalBlock({
  title,
  subtitle,
  palette,
  values,
  selectedIter,
  formatter,
  deltaFormatter,
  deltaUnit = '',
}) {
  const count = values.length;
  const firstVal = count > 0 ? values[0] : null;
  const lastVal = count > 0 ? values[count - 1] : null;
  const deltaVal = count > 1 ? (lastVal - firstVal) : null;

  return h('div', {
    style: {
      background: 'var(--cx-panel-bg)',
      border: `1px solid ${palette.line}33`,
      borderTop: `2px solid ${palette.line}`,
      borderRadius: 2,
      padding: '14px 16px',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      height: '100%',
      boxSizing: 'border-box',
      boxShadow: `0 4px 20px ${palette.line}0a`,
    },
  },
    // Top Section: Header & Subtitle
    h('div', null,
      h('div', {
        style: {
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 8,
          borderBottom: '1px solid var(--cx-edge-soft)',
          paddingBottom: 6,
        },
      },
        h('span', {
          style: {
            fontFamily: 'var(--cx-mono)',
            fontSize: 12,
            fontWeight: 700,
            color: palette.line,
            textTransform: 'uppercase',
            letterSpacing: '0.12em',
          },
        }, title),
        h('span', {
          style: {
            fontFamily: 'var(--cx-mono)',
            fontSize: 12,
            color: 'var(--cx-text-faint)',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
          },
        }, subtitle),
      ),

      // Visual Convergence Chart
      h('div', { style: { marginBottom: 12, padding: '4px 0' } },
        h(ConvergenceChart, {
          values,
          palette,
          selectedIter,
          yFormat: formatter,
          height: 125,
        })
      ),

      // Iteration by iteration listing
      h('div', {
        style: {
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
          marginBottom: 12,
          padding: '8px 10px',
          background: 'rgba(0,0,0,0.2)',
          borderRadius: 2,
          border: '1px solid var(--cx-edge-soft)',
        },
      },
        h('div', {
          style: {
            fontFamily: 'var(--cx-mono)',
            fontSize: 12,
            color: 'var(--cx-text-faint)',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            marginBottom: 2,
          },
        }, 'Iteration Sequence'),
        values.map((v, i) => {
          const isSelected = selectedIter != null && i === selectedIter;
          return h('div', {
            key: i,
            style: {
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontFamily: 'var(--cx-mono)',
              fontSize: 12,
              padding: '2px 0',
              borderBottom: i < values.length - 1 ? '1px dashed rgba(255,255,255,0.05)' : 'none',
            },
          },
            h('span', {
              style: {
                color: isSelected ? palette.line : 'var(--cx-text-faint)',
                fontWeight: isSelected ? 700 : 400,
              },
            }, `ITER ${String(i).padStart(2, '0')}${isSelected ? ' ★' : ''}`),
            h('span', {
              style: {
                color: isSelected ? palette.line : 'var(--cx-text)',
                fontWeight: 600,
              },
            }, formatter(v)),
          );
        }),
      ),
    ),

    // Bottom Summary: FIRST / LAST / DELTA Footer
    h('div', {
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 8,
        paddingTop: 8,
        borderTop: `1px solid ${palette.line}22`,
      },
    },
      h('div', null,
        h('div', {
          style: {
            fontFamily: 'var(--cx-mono)', fontSize: 12,
            color: 'var(--cx-text-faint)', textTransform: 'uppercase',
            letterSpacing: '0.1em', marginBottom: 2,
          },
        }, 'FIRST'),
        h('div', {
          style: { fontFamily: 'var(--cx-mono)', fontSize: 12, fontWeight: 600, color: 'var(--cx-text)' },
        }, firstVal != null ? formatter(firstVal) : EM),
      ),
      h('div', null,
        h('div', {
          style: {
            fontFamily: 'var(--cx-mono)', fontSize: 12,
            color: 'var(--cx-text-faint)', textTransform: 'uppercase',
            letterSpacing: '0.1em', marginBottom: 2,
          },
        }, 'LAST'),
        h('div', {
          style: { fontFamily: 'var(--cx-mono)', fontSize: 12, fontWeight: 600, color: palette.line },
        }, lastVal != null ? formatter(lastVal) : EM),
      ),
      h('div', null,
        h('div', {
          style: {
            fontFamily: 'var(--cx-mono)', fontSize: 12,
            color: 'var(--cx-text-faint)', textTransform: 'uppercase',
            letterSpacing: '0.1em', marginBottom: 2,
          },
        }, 'DELTA'),
        h('div', {
          style: {
            fontFamily: 'var(--cx-mono)', fontSize: 12, fontWeight: 600,
            color: deltaColor(deltaVal),
          },
        }, deltaVal != null ? (deltaFormatter ? deltaFormatter(deltaVal) : fmtDelta(deltaVal, deltaUnit)) : EM),
      ),
    ),
  );
}

// ─── Main GA / MILP Console Component ───────────────────────────────────────
export default function GaMilp(props) {
  const optStateProp = props && props.optimizationState;
  const hookState = useOptimizationState();
  const optState = optStateProp || hookState;

  const gbl = optState.global || {};
  const rawIters = optState.iterations || [];
  const scorecards = optState.scorecards || [];

  const iterSelMeta = gbl.iteration_selection || {};
  const pipelineSelectedIter = selectedIterationOf(optState) ?? 0;
  const iterCount = scorecards.length > 0 ? scorecards.length : rawIters.length;
  const overallTone = iterCount > 0 ? 'available' : 'no_data';
  const runId = gbl.run_id || '—';
  const globalRuntime = gbl.health_status?.runtime_seconds ?? gbl.runtime ?? null;

  // Selected iteration data
  const selectedSC = useMemo(() =>
    scorecards.find(s => s.iteration === pipelineSelectedIter) || scorecards[0] || null,
    [scorecards, pipelineSelectedIter]
  );

  // Dynamic series across all available iterations
  const scoreSeries = useMemo(() => {
    if (scorecards.length > 0) return scorecards.map(s => s.convergence_score ?? 0);
    return rawIters.map(i => i.score ?? 0);
  }, [scorecards, rawIters]);

  const globalCovSeries = useMemo(() => {
    if (scorecards.length > 0) return scorecards.map(s => s.global_demand_weighted_coverage ?? s.average_regional_coverage ?? 0);
    return rawIters.map(i => i.globalCoverage ?? i.coverage ?? 0);
  }, [scorecards, rawIters]);

  const profitSeries = useMemo(() => {
    if (scorecards.length > 0) return scorecards.map(s => s.weekly_profit ?? 0);
    return rawIters.map(i => i.profit ?? 0);
  }, [scorecards, rawIters]);

  const serviceSeries = useMemo(() => {
    if (scorecards.length > 0) return scorecards.map(s => s.services_deployed ?? 0);
    return rawIters.map(i => i.servicesDeployed ?? 0);
  }, [scorecards, rawIters]);

  return h(F, null,
    h(PageHead, {
      section: 'AI Operations',
      eyebrow: 'GA · MILP',
      title: 'GA / MILP Optimization Console',
      subtitle: 'Focused optimization evidence and convergence analysis across pipeline iterations. Sourced directly from pipeline_output.json.',
      pills: [
        { tone: overallTone, label: iterCount + ' iterations' },
        { tone: 'selected', label: 'ITER ' + String(pipelineSelectedIter).padStart(2, '0') + ' SELECTED' },
        { tone: 'active', label: 'score ' + (selectedSC?.convergence_score?.toFixed(3) ?? EM) },
        { tone: globalRuntime != null ? 'available' : 'no_data', label: globalRuntime != null ? fmtSec(globalRuntime) + ' total' : 'runtime N/A' },
      ],
    }),

    h('div', { className: 'cx-page-body' },

      // ── KPI Strip ────────────────────────────────────────────────────────
      h('div', { className: 'cx-grid-12', style: { marginBottom: 16 } },
        h('div', { className: 'cx-span-2' },
          h(InstrumentPanel, { title: 'Iterations', right: 'audit trail' },
            h(Stat, { k: 'iters', v: String(iterCount), variant: 'accent', sub: 'total run' })
          )
        ),
        h('div', { className: 'cx-span-2' },
          h(InstrumentPanel, { title: 'Selected', right: 'canonical pick' },
            h(Stat, {
              k: 'sel',
              v: 'ITER ' + String(pipelineSelectedIter).padStart(2, '0'),
              variant: 'good',
              sub: iterSelMeta.selection_method?.replace(/_/g, ' ') || 'deterministic',
            })
          )
        ),
        h('div', { className: 'cx-span-2' },
          h(InstrumentPanel, { title: 'Final Score', right: 'selected iter' },
            h(Stat, {
              k: 'score',
              v: selectedSC?.convergence_score != null ? selectedSC.convergence_score.toFixed(3) : EM,
              sub: 'convergence score',
            })
          )
        ),
        h('div', { className: 'cx-span-2' },
          h(InstrumentPanel, { title: 'Global Coverage', right: 'demand-weighted' },
            h(Stat, {
              k: 'cov',
              v: selectedSC?.global_demand_weighted_coverage != null
                ? fmtPct(selectedSC.global_demand_weighted_coverage)
                : EM,
              sub: gbl.coverage_target ? 'target ' + gbl.coverage_target + '%' : 'demand-weighted',
            })
          )
        ),
        h('div', { className: 'cx-span-2' },
          h(InstrumentPanel, { title: 'Weekly P&L', right: 'selected iter' },
            h(Stat, {
              k: 'profit',
              v: selectedSC?.weekly_profit != null ? fmtUsd(selectedSC.weekly_profit) : EM,
              variant: 'good',
              sub: 'per week',
            })
          )
        ),
        h('div', { className: 'cx-span-2' },
          h(InstrumentPanel, { title: 'Total Runtime', right: 'pipeline wall-clock' },
            h(Stat, {
              k: 'time',
              v: globalRuntime != null ? fmtSec(globalRuntime) : EM,
              sub: 'health_status.runtime_seconds',
            })
          )
        ),
      ),

      // ── Main Four Analytical Blocks (Strict 2×2 Desktop Grid) ────────────
      h('div', {
        className: 'ga-milp-grid',
        style: {
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 16,
          marginBottom: 16,
        },
      },
        // Block 1: CONVERGENCE · SCORE
        h(AnalyticalBlock, {
          title: 'CONVERGENCE · SCORE',
          subtitle: 'AUDIT TRAIL',
          palette: CHART.score,
          values: scoreSeries,
          selectedIter: pipelineSelectedIter,
          formatter: v => Number(v).toFixed(3),
          deltaFormatter: v => fmtDelta(v, '', 3),
        }),

        // Block 2: COVERAGE EVOLUTION
        h(AnalyticalBlock, {
          title: 'COVERAGE EVOLUTION',
          subtitle: '% · GLOBAL DEMAND-WEIGHTED',
          palette: CHART.coverage,
          values: globalCovSeries,
          selectedIter: pipelineSelectedIter,
          formatter: v => fmtPct(v, 1),
          deltaFormatter: v => fmtDelta(v, ' pp', 1),
        }),

        // Block 3: PROFIT EVOLUTION
        h(AnalyticalBlock, {
          title: 'PROFIT EVOLUTION',
          subtitle: 'USD / WEEK',
          palette: CHART.profit,
          values: profitSeries,
          selectedIter: pipelineSelectedIter,
          formatter: v => fmtUsd(v),
          deltaFormatter: v => fmtDeltaUsd(v),
        }),

        // Block 4: SERVICES DEPLOYED
        h(AnalyticalBlock, {
          title: 'SERVICES DEPLOYED',
          subtitle: 'COUNT',
          palette: CHART.services,
          values: serviceSeries,
          selectedIter: pipelineSelectedIter,
          formatter: v => fmtNum(v),
          deltaFormatter: v => fmtDelta(v, '', 0),
        }),
      ),

      // ── GA generation playback (runs that record generation_history) ─────
      h('div', { style: { marginBottom: 16 } },
        h(InstrumentPanel, { title: 'GA generation playback', right: 'service GA · per regional agent' },
          h(GaPlayback, { raw: optState.raw, selectedIteration: pipelineSelectedIter })
        )
      ),

      // ── Provenance Footer ────────────────────────────────────────────────
      h(Provenance, {
        source: 'pipeline_output.json · iteration_audit + iteration_results + scorecards',
        sourceStatus: iterCount > 0 ? 'available' : 'no_data',
        attribution: runId + ' · ITER ' + String(pipelineSelectedIter).padStart(2, '0') + ' SELECTED · ' + iterCount + ' iters',
        license: 'Internal artifact',
        recordCount: iterCount,
        snapshotId: gbl.evaluated_at ? new Date(gbl.evaluated_at).toLocaleTimeString() : undefined,
      }),
    ),
  );
}
