/**
 * TelemetryRail
 * -------------
 * The single persistent top-of-app telemetry band. Three regions:
 *   - identity + status (brand, regime chip, system state)
 *   - inline run/optimizer/agents/iter/maritime/ws telemetry
 *   - right-aligned last-update timestamp
 *
 * Reads ONLY from props. No fetches. No business logic.
 */

import { Pill, State, Dot } from './p12.jsx';

function fmtTime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  } catch (_) { return String(iso); }
}

export default function TelemetryRail({ optimizationState, maritimeOverview, runtime }) {
  const wsConnected = !!optimizationState?.isConnected;
  const sm = runtime?.global || optimizationState?.global || {};
  const iterCount = (runtime?.iterations?.length) || (optimizationState?.iterations?.length) || 0;
  const selIter = sm.iter ?? sm.selected_iteration;
  const status = String(sm.status || '').toLowerCase();
  const systemReady = status === 'complete';
  const overallLabel =
    systemReady ? 'SYSTEM READY' :
    status === 'running' ? 'RUNNING' :
    status === 'failed' || status === 'error' ? 'FAILED' :
    status === 'partial' || status === 'degraded' ? 'DEGRADED' :
    'STATE UNKNOWN';

  const mi = maritimeOverview;
  const miState = mi?.enabled
    ? (mi?.overall_state || 'enabled')
    : (mi?.enabled === false ? 'DISABLED' : 'NOT OBSERVED');

  const lastEval = mi?.evaluated_at;
  const lastEvalStr = lastEval ? fmtTime(lastEval) : '—';

  return (
    <div className="cx-telemetry" role="status" aria-label="System telemetry">
      <span className="brand">
        <span className="brand-mark" aria-hidden="true" />
        AI VESSEL ROUTING INTELLIGENCE
      </span>
      <span className="sub">v2.0</span>
      <span className="sep" aria-hidden="true" />
      <span className="kv">
        <span className={`dot ${systemReady ? 'green' : status === 'running' ? 'cyan' : status === 'failed' ? 'red' : 'slate'}`} />
        <span className={`v ${systemReady ? 'green' : status === 'running' ? 'cyan' : status === 'failed' ? 'red' : 'muted'}`}>
          {overallLabel}
        </span>
      </span>
      <span className="kv hide-md">
        <span className="k">RUN</span>
        <span className="v muted">03</span>
      </span>
      <span className="kv">
        <span className="k">OPTIMIZER</span>
        <span className="v">{systemReady ? 'CONVERGED' : status === 'running' ? 'RUNNING' : (sm.status || 'IDLE').toUpperCase()}</span>
      </span>
      <span className="kv hide-md">
        <span className="k">AGENTS</span>
        <span className="v">GA + MILP</span>
      </span>
      <span className="kv hide-md">
        <span className="k">ITER</span>
        <span className="v">{iterCount || '—'}</span>
      </span>
      <span className="kv hide-md">
        <span className="k">SELECTED</span>
        <span className="v accent">
          {selIter != null ? `iter ${String(selIter).padStart(2, '0')}` : '—'}
        </span>
      </span>
      <span className="kv">
        <span className="k">MARITIME</span>
        <span className={`v ${mi?.enabled ? 'green' : 'muted'}`}>{String(miState).toUpperCase()}</span>
      </span>
      <span className="kv">
        <span className="k">WS</span>
        <span className={`v ${wsConnected ? 'green' : 'amber'}`}>
          {wsConnected ? 'LINK' : 'OFFLINE'}
        </span>
      </span>
      <span className="right">
        <span className="kv">
          <span className="k">LAST UPDATE</span>
          <span className="v muted">{lastEvalStr}</span>
        </span>
      </span>
    </div>
  );
}
