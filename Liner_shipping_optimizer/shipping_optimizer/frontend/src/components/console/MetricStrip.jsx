/**
 * MetricStrip
 * -----------
 * Persistent numeric telemetry strip immediately below the top
 * status bar. Renders the "command telemetry" values (ports,
 * lanes, services, weekly TEU, runtime, iter, coverage, etc).
 *
 * Reads ONLY from props. No fetches.
 */

function fmtNum(v, opts = {}) {
  if (v == null) return '—';
  if (opts.usd) {
    if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
    if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
    return `$${Math.round(v)}`;
  }
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return String(Math.round(v));
}

export default function MetricStrip({ optimizationState, runtime }) {
  const sm = runtime?.global || optimizationState?.global || {};
  const iterCount = (runtime?.iterations?.length) || (optimizationState?.iterations?.length) || 0;
  const selIter = sm.iter ?? sm.selected_iteration;
  const coverage = sm.coverage;
  const weeklyDemand = sm.weeklyDemand;
  const weeklyProfit = sm.weeklyProfit;
  const runtimeSec = sm.runtime;
  const totalServices = sm.totalServices;

  const segs = [
    // A missing figure is shown as unavailable, never as a remembered demo value.
    { k: 'PORTS',     v: sm.ports != null ? fmtNum(sm.ports) : '—' },
    { k: 'LANES',     v: sm.lanes != null ? fmtNum(sm.lanes) : '—' },
    { k: 'SERVICES',  v: sm.services != null ? fmtNum(sm.services) : (totalServices != null ? fmtNum(totalServices) : '—') },
    { k: 'WEEKLY TEU', v: weeklyDemand != null ? fmtNum(weeklyDemand) : '—' },
    { k: 'RUNTIME',   v: runtimeSec != null ? `${Number(runtimeSec).toFixed(1)}s` : '—' },
    { k: 'ITER',      v: iterCount > 0 ? iterCount : '—', sub: `sel ${selIter != null ? String(selIter).padStart(2, '0') : '—'}` },
    { k: 'COVERAGE',  v: coverage != null ? `${Number(coverage).toFixed(1)}%` : '—' },
    { k: 'PROFIT / WK', v: weeklyProfit != null ? fmtNum(weeklyProfit, { usd: true }) : '$—', accent: true },
  ];

  return (
    <div className="cx-metric-strip" role="contentinfo" aria-label="Operational metrics">
      {segs.map((s) => (
        <span key={s.k} className="seg">
          <span className="k">{s.k}</span>
          <span className={`v ${s.accent ? 'accent' : ''}`}>{s.v}</span>
          {s.sub && <span className="sub">{s.sub}</span>}
        </span>
      ))}
      <span className="right" />
    </div>
  );
}
