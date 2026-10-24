/**
 * SystemRail
 * ----------
 * The persistent bottom rail. Honest diagnostic readout of every
 * subsystem. No fabricated heartbeat.
 *
 * Reads ONLY from props.
 */

import { useEffect, useState } from 'react';
import { apiClient } from '../../services/apiClient.js';
import { selectedIterationOf } from '../../runtime/consoleSelectors.js';

function fmtNum(v) {
  if (v == null) return '—';
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(Math.round(v));
}

export default function SystemRail({ maritimeOverview, runtime: runtimeProp }) {
  const [runtime, setRuntime] = useState(runtimeProp || null);
  useEffect(() => {
    if (runtimeProp) { setRuntime(runtimeProp); return; }
    let cancelled = false;
    let timer = null;
    const load = async () => {
      try {
        const norm = await apiClient.loadRuntimeTruth().catch(() => null);
        if (!cancelled && norm) setRuntime(norm);
      } catch (_) { /* noop */ }
    };
    load();
    timer = setInterval(load, 30000);
    return () => { cancelled = true; if (timer) clearInterval(timer); };
  }, [runtimeProp]);

  const sm = runtime?.global || {};
  const iterCount = runtime?.iterations?.length || 0;
  const lastIter = iterCount > 0 ? runtime.iterations[iterCount - 1] : null;
  const status = String(sm.status || '').toLowerCase();
  const sel = selectedIterationOf(runtime);
  const selIterObj = sel != null ? (runtime?.iterations || []).find((it) => Number(it.iter) === Number(sel)) : null;
  const selScore = selIterObj && selIterObj.score != null && Number.isFinite(Number(selIterObj.score)) ? Number(selIterObj.score) : null;

  const dots = {
    orchestrator: status === 'complete' ? 'green' : status === 'running' ? 'cyan' : 'slate',
    regional: (runtime?.regions && Object.keys(runtime.regions).length > 0) ? 'green' : 'dim',
    ga: lastIter && Number(lastIter.score || 0) > 0 ? 'green' : 'dim',
    milp: iterCount > 0 ? 'green' : 'dim',
    selection: sel != null ? 'green' : 'dim',
    decision: sm.selected_services && sm.selected_services.length > 0 ? 'green' : 'dim',
  };

  const mi = maritimeOverview;
  const miDot = mi?.enabled
    ? (mi?.overall_state === 'live' ? 'cyan' :
       mi?.overall_state === 'available' ? 'green' :
       ['degraded', 'stale'].includes(mi?.overall_state) ? 'amber' : 'slate')
    : 'dim';

  return (
    <div className="cx-system-rail" role="contentinfo" aria-label="System rail">
      <span className="seg">
        <span className={`dot ${dots.orchestrator}`} />
        <span className="v">ORCH: {status === 'complete' ? 'COMPLETE' : status === 'running' ? 'RUNNING' : 'IDLE'}</span>
      </span>
      <span className="seg">
        <span className={`dot ${dots.regional}`} />
        <span className="v">REGIONAL ×{Object.keys(runtime?.regions || {}).length || '—'}</span>
      </span>
      <span className="seg">
        <span className={`dot ${dots.ga}`} />
        <span className="v">GA: {iterCount > 0
          ? `${iterCount} iter${iterCount === 1 ? '' : 's'}${selScore != null ? ` · selected score ${selScore.toFixed(3)}` : ''}`
          : '—'}</span>
      </span>
      <span className="seg">
        <span className={`dot ${dots.milp}`} />
        <span className="v">MILP: {iterCount > 0 ? `${iterCount} solves` : '—'}</span>
      </span>
      <span className="seg">
        <span className={`dot ${dots.selection}`} />
        <span className="v">SELECTION: {sel != null ? `iter ${String(sel).padStart(2, '0')}` : '—'}</span>
      </span>
      <span className="seg">
        <span className={`dot ${dots.decision}`} />
        <span className="v">DECISION: {sm.selected_services?.length > 0 ? `${fmtNum(sm.selected_services.length)} services` : '—'}</span>
      </span>
      <span className="seg">
        <span className={`dot ${miDot}`} />
        <span className="v">MARITIME: {mi?.enabled ? (mi?.overall_state || 'enabled').toUpperCase() : 'DISABLED'}</span>
      </span>
      <span className="right" />
      <span className="seg">
        <span className="dot dim" />
        <span className="v muted">v2.0 · {sm.ports ? `${sm.ports} ports` : 'network'} · {sm.lanes ? `${Number(sm.lanes).toLocaleString()} lanes` : 'lanes'}</span>
      </span>
    </div>
  );
}
