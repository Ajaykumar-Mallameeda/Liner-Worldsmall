/**
 * PipelineOps -- Phase 12 REVISION
 * --------------------------------
 * The pipeline operations instrument. Shows the full pipeline
 * run as a deterministic sequence of stages with honest status
 * per stage. No fake running states; the data is from the
 * orchestrator / pipeline audit.
 *
 * Data contracts UNCHANGED.
 */

import { useMemo, createElement, Fragment } from 'react';
import { useOptimizationState } from '../../hooks/useOptimizationState.js';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Pill, Kv, Stat, Empty, Tag, Dot, Provenance } from '../../components/console/p12.jsx';
import { selectedIterationOf } from '../../runtime/consoleSelectors.js';
const h = createElement;
const F = Fragment;

const EM = '—';
function fmtTime(iso) {
  if (!iso) return EM;
  try { return new Date(iso).toISOString().slice(0, 19).replace('T', ' '); }
  catch (_) { return String(iso); }
}
function fmtNum(v) {
  if (v == null) return EM;
  if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (v >= 1e3) return (v / 1e3).toFixed(0) + 'K';
  return String(Math.round(v));
}
function fmtUsd(v) {
  if (v == null) return EM;
  if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
  if (v >= 1e3) return '$' + (v / 1e3).toFixed(0) + 'K';
  return '$' + Math.round(v);
}

const STAGE_ORDER = [
  { id: 'inputs',                label: 'Inputs',                 desc: 'ports, demand, vessel registry loaded' },
  { id: 'regional_decomposition',label: 'Regional decomposition', desc: 'ports split across regional agents' },
  { id: 'service_generation',    label: 'Service generation',     desc: 'candidates, vessel class + ports' },
  { id: 'ga',                    label: 'GA optimization',        desc: 'evolutionary selection per region' },
  { id: 'milp',                  label: 'MILP solve',             desc: 'deterministic final pass' },
  { id: 'iteration_selection',   label: 'Iteration selection',    desc: 'canonical pick across iterations' },
  { id: 'validation',            label: 'Validation',             desc: 'shadow-modeling + reconcilers' },
  { id: 'final_decision',        label: 'Final decision',         desc: 'audit trail emitted' },
];

function statusFor(stage, optState) {
  const sm = optState.global || {};
  const iters = optState.iterations || [];
  const regions = optState.regions || {};
  const sel = selectedIterationOf(optState);
  switch (stage) {
    case 'inputs':                 return { tone: sm.weeklyDemand != null ? 'completed' : 'unavailable', note: sm.weeklyDemand != null ? ('demand ' + fmtNum(sm.weeklyDemand) + ' TEU/wk') : 'no demand on record' };
    case 'regional_decomposition': return { tone: Object.keys(regions).length > 0 ? 'completed' : 'unavailable', note: Object.keys(regions).length > 0 ? (Object.keys(regions).length + ' regions') : 'no regions' };
    case 'service_generation':     return { tone: (sm.selected_services || []).length > 0 ? 'completed' : 'unavailable', note: (sm.selected_services || []).length > 0 ? ((sm.selected_services || []).length + ' selected') : 'no selected services' };
    case 'ga':                     return { tone: iters.length > 0 ? 'completed' : 'unavailable', note: iters.length > 0 ? (iters.length + ' iterations') : 'no iteration audit' };
    case 'milp':                   return { tone: iters.length > 0 ? 'completed' : 'unavailable', note: iters.length > 0 ? ('final pass: iter ' + String(iters[iters.length - 1].iter).padStart(2, '0')) : 'no MILP' };
    case 'iteration_selection':    return { tone: sel != null ? 'selected' : 'unavailable', note: sel != null ? ('selected iter ' + String(sel).padStart(2, '0')) : 'no selection' };
    case 'validation':             return { tone: sm.coverage != null ? 'completed' : 'unavailable', note: sm.coverage != null ? ('coverage ' + Number(sm.coverage).toFixed(1) + '%') : 'no validation' };
    case 'final_decision':         return { tone: sm.weeklyProfit != null ? 'selected' : 'unavailable', note: sm.weeklyProfit != null ? (fmtUsd(sm.weeklyProfit) + '/wk') : 'no decision' };
    default: return { tone: 'unavailable', note: '' };
  }
}

export default function PipelineOps(props) {
  const optStateProp = props && props.optimizationState;
  const runtimeProp = props && props.runtime;
  const maritimeOverview = props && props.maritimeOverview;
  const hookState = useOptimizationState();
  const optState = optStateProp || hookState;
  const sm = (runtimeProp && runtimeProp.global) || optState.global || {};
  const iters = (runtimeProp && runtimeProp.iterations) || optState.iterations || [];

  const stageRows = useMemo(function() {
    return STAGE_ORDER.map(function(s) { return Object.assign({}, s, statusFor(s.id, optState)); });
  }, [optState]);

  const runConfig = optState.config || null;
  const runId = sm.run_id || sm.runId || null;
  const completed = stageRows.every(function(r) { return r.tone === 'completed' || r.tone === 'selected'; });
  const stagesOk = stageRows.filter(function(r) { return r.tone === 'completed' || r.tone === 'selected'; }).length;

  return h(F, null,
    h(PageHead, {
      section: 'AI Operations',
      eyebrow: 'Pipeline',
      title: 'Pipeline Operations',
      subtitle: 'The deterministic pipeline that produced the current selection. Every stage status is derived from the audit trail; nothing is fabricated.',
      pills: [
        { tone: completed ? 'converged' : 'partial', label: completed ? 'complete' : 'partial' },
        { tone: runId ? 'available' : 'no_data', label: runId ? ('run ' + runId) : 'no run' },
        { tone: iters.length > 0 ? 'available' : 'no_data', label: iters.length + ' iterations' },
      ],
    }),

    h('div', { className: 'cx-page-body' },

      h('div', { className: 'cx-grid-12' },
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Run', right: 'id' },
            h(Stat, { k: 'run', v: runId || EM, sub: runId ? 'id' : 'not observed' })
          )
        ),
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Stages', right: 'observed / total' },
            h(Stat, { k: 'stages', v: stagesOk + ' / ' + stageRows.length, variant: completed ? 'good' : 'muted', sub: 'observed' })
          )
        ),
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Iterations', right: 'audit trail' },
            h(Stat, { k: 'iters', v: fmtNum(iters.length), sub: 'GA generations' })
          )
        ),
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Final Profit', right: '/ week' },
            h(Stat, { k: 'profit', v: sm.weeklyProfit != null ? fmtUsd(sm.weeklyProfit) : EM, variant: 'accent', sub: 'per week' })
          )
        )
      ),

      h(InstrumentPanel, {
        title: 'Stage Ladder',
        right: 'each stage is a real orchestrator phase',
        bodyPadding: 'flush',
      },
        h('div', { className: 'cx-rows' },
          stageRows.map(function(r, i) {
            return h('div', { key: r.id, className: 'cx-row', style: { padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 10 } },
              h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)', minWidth: 18 } }, String(i + 1).padStart(2, '0')),
              h('span', { style: { display: 'flex', alignItems: 'center', gap: 6, minWidth: 200 } },
                h(Dot, { tone: r.tone }),
                h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text)', textTransform: 'uppercase', letterSpacing: '0.14em' } }, r.label)
              ),
              h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-dim)', flex: 1 } }, r.desc),
              h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text)' } }, r.note),
              h('span', { style: { minWidth: 88, textAlign: 'right' } },
                h(Tag, { variant: r.tone === 'selected' ? 'purple' : (r.tone === 'completed' ? 'good' : (r.tone === 'unavailable' ? 'warn' : 'accent')) }, r.tone)
              )
            );
          })
        )
      ),

      h('div', { className: 'cx-grid-12' },
        h('div', { className: 'cx-span-6' },
          h(InstrumentPanel, {
            title: 'Run Configuration',
            right: 'the inputs that produced this selection',
            bodyPadding: 'flush',
          },
            !runConfig
              ? h(Empty, { tone: 'no_data', label: 'no config', title: 'No run configuration on record' })
              : h('pre', { className: 'p12-pre', style: { margin: 0, padding: '10px 12px', maxHeight: 360, overflow: 'auto' } },
                  JSON.stringify(runConfig, null, 2)
                )
          )
        ),
        h('div', { className: 'cx-span-6' },
          h(InstrumentPanel, {
            title: 'Run Metadata',
            right: 'identifiers, timestamps, audit',
            bodyPadding: 'flush',
          },
            h('div', { className: 'p12-kv-grid', style: { padding: '10px 12px' } },
              h(Kv, { k: 'run id', v: runId || EM }),
              h(Kv, { k: 'created', v: fmtTime(sm.created_at || sm.timestamp) }),
              h(Kv, { k: 'selected iter', v: sm.iter != null ? ('iter ' + String(sm.iter).padStart(2, '0')) : EM }),
              h(Kv, { k: 'seed', v: sm.seed != null ? String(sm.seed) : EM }),
              h(Kv, { k: 'runtime', v: sm.runtime_seconds != null ? (Number(sm.runtime_seconds).toFixed(1) + 's') : EM }),
              h(Kv, { k: 'evaluated', v: fmtTime(sm.evaluated_at) }),
              h(Kv, { k: 'coverage', v: sm.coverage != null ? (Number(sm.coverage).toFixed(1) + '%') : EM }),
              h(Kv, { k: 'final profit', v: sm.weeklyProfit != null ? fmtUsd(sm.weeklyProfit) : EM })
            )
          )
        )
      ),

      h(Provenance, {
        source: 'pipeline_output.json (run metadata + iteration_audit)',
        sourceStatus: runId ? 'available' : 'no_data',
        attribution: 'Deterministic orchestrator',
        license: 'Internal artifact',
        recordCount: iters.length,
        snapshotId: sm.run_id,
      })
    )
  );
}
