/**
 * Header — Phase 12
 * -----------------
 * Compact top-of-app header. Three clear bands:
 *   1. System identity (brand, WS link, optimizer state)
 *   2. Key metrics strip (ports, lanes, services, demand, …)
 *   3. Global controls (play, flows, reset, fullscreen, demo)
 *
 * Reads ONLY from the parent — no fetches, no business logic.
 */

import { useMemo } from 'react';
import { Pill } from '../console/p12.jsx';

export default function Header({
  optimizationState,
  startOptimization,
  isPipelineRunning,
  showFlows,
  onToggleFlows,
  onReset,
  onToggleFullscreen,
  presentationMode,
  onToggleDemo,
  demoMode,
  onExport,
}) {
  const wsConnected = !!optimizationState?.isConnected;
  const g = optimizationState?.global || {};
  const iterCount = optimizationState?.iterations?.length || 0;
  const selIter = g.iter ?? g.selected_iteration;
  const overallState = String(g.status || '').toLowerCase();
  const optimizerTone =
    overallState === 'complete' ? 'converged' :
    overallState === 'running' ? 'active' :
    overallState === 'failed'  ? 'error'   :
    overallState === 'partial' ? 'degraded' :
    'unknown';

  const metrics = useMemo(() => ([
    { label: 'ports',     v: g.ports },
    { label: 'lanes',     v: g.lanes },
    { label: 'services',  v: g.services },
    { label: 'weekly',    v: g.weeklyDemand != null ? `${(g.weeklyDemand / 1000).toFixed(0)}K` : null, sub: 'TEU' },
    { label: 'runtime',   v: g.runtime != null ? `${Number(g.runtime).toFixed(1)}s` : null },
    { label: 'iter',      v: iterCount, sub: `sel ${selIter != null ? selIter : '—'}` },
    { label: 'coverage',  v: g.coverage != null ? `${Number(g.coverage).toFixed(1)}%` : null },
    { label: 'profit/wk', v: g.weeklyProfit != null ? `$${(g.weeklyProfit / 1e3).toFixed(0)}K` : null, accent: true },
  ]), [g, iterCount, selIter]);

  return (
    <header
      className="dashboard-header"
      style={{
        background: 'rgba(2, 9, 18, 0.95)',
        borderBottom: '1px solid var(--p12-edge)',
        backdropFilter: 'blur(20px)',
        flexShrink: 0,
        minHeight: 60,
      }}
    >
      {/* Row 1: identity + controls */}
      <div
        className="flex items-center justify-between"
        style={{ padding: '8px 16px 6px 16px', borderBottom: '1px solid var(--p12-divider)' }}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div
            className="flex items-center justify-center"
            aria-hidden="true"
            style={{
              width: 30, height: 30,
              background: 'rgba(0, 212, 255, 0.08)',
              border: '1px solid rgba(0, 212, 255, 0.35)',
              borderRadius: 4,
              color: 'var(--p12-cyan)',
              fontFamily: 'var(--p12-font-mono)',
              fontSize: 16, fontWeight: 700,
              boxShadow: '0 0 12px rgba(0, 212, 255, 0.20)',
            }}
          >
            ⬡
          </div>
          <div className="min-w-0">
            <div
              className="p12-title"
              style={{ fontFamily: 'var(--p12-font-mono)', fontSize: 12, letterSpacing: '0.16em', textTransform: 'uppercase' }}
            >
              AI Vessel Routing System
            </div>
            <div
              className="p12-meta"
              style={{ marginTop: 2, fontSize: 12, color: 'var(--p12-ink-faint)' }}
            >
              Multi-Agent Liner Shipping Optimizer
            </div>
          </div>
          <div className="flex items-center gap-2" style={{ marginLeft: 16 }}>
            <Pill tone={wsConnected ? 'connected' : 'offline'}>
              {wsConnected ? 'WS · LINK' : 'WS · OFFLINE'}
            </Pill>
            <Pill tone={optimizerTone}>
              {overallState === 'complete' ? 'converged' : (g.status || 'state unknown')}
            </Pill>
            {isPipelineRunning && (
              <Pill tone="active" dot>
                {optimizationState?.currentStage || 'running'}
              </Pill>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={startOptimization}
            disabled={isPipelineRunning}
            className="p12-btn p12-btn--accent"
            style={{ opacity: isPipelineRunning ? 0.6 : 1, cursor: isPipelineRunning ? 'not-allowed' : 'pointer' }}
          >
            {isPipelineRunning ? '◐ Running' : '▶ Play'}
          </button>
          <button type="button" onClick={onToggleFlows} className={`p12-btn ${showFlows ? 'p12-btn--active' : ''}`}>
            {showFlows ? '⏻ Flows' : '⊝ Flows'}
          </button>
          <button type="button" onClick={onReset} className="p12-btn">⊡ Reset</button>
          <button
            type="button"
            onClick={onToggleFullscreen}
            className={`p12-btn ${presentationMode ? 'p12-btn--active' : ''}`}
          >
            ⛶ Fullscreen
          </button>
          <button
            type="button"
            onClick={onToggleDemo}
            className={`p12-btn ${demoMode ? 'p12-btn--active' : ''}`}
          >
            {demoMode ? '◐ Demo' : '▶ Demo'}
          </button>
          <button type="button" onClick={onExport} className="p12-btn">↓ Export</button>
        </div>
      </div>

      {/* Row 2: metric strip */}
      <div
        className="flex items-center gap-5"
        style={{ padding: '6px 16px', overflowX: 'auto' }}
      >
        {metrics.map((m) => (
          <div key={m.label} className="flex items-baseline gap-2" style={{ whiteSpace: 'nowrap' }}>
            <span className="p12-meta" style={{ minWidth: 60 }}>{m.label}</span>
            <span
              className="p12-data"
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: m.accent ? 'var(--p12-cyan)' : 'var(--p12-ink)',
              }}
            >
              {m.v != null ? m.v : '—'}
            </span>
            {m.sub && <span className="p12-meta" style={{ fontSize: 12 }}>{m.sub}</span>}
          </div>
        ))}
      </div>
    </header>
  );
}
