/**
 * CommandCenterShell.jsx
 * ----------------------
 * Unified single-header command shell for the AI Vessel Routing System.
 *
 * BLOCK 1 COMPLIANCE:
 * - Single compact header band (Brand + System Telemetry + Status Chips + Action Controls)
 * - Removed the second metric strip entirely (PORTS, LANES, WEEKLY TEU, RUNTIME, etc.)
 * - Zero wasted height footprint; height redistributed to dominant map & intelligence panels.
 */

import React, { useState, useEffect } from 'react';
import ConsoleSidebar from './ConsoleSidebar.jsx';
import CommandCenter from '../../views/console/CommandCenter.jsx';
import { Pill } from './p12.jsx';

function nowUtc() {
  const d = new Date();
  return d.toTimeString().slice(0, 8);
}

export default function CommandCenterShell({
  activeNav = 'command',
  onNavChange,
  optimizationState,
  runtime,
  maritimeOverview,
  isPipelineRunning = false,
  startOptimization,
  presentationMode = false,
  onToggleFullscreen,
  showFlows = true,
  onToggleFlows,
  onReset,
  demoMode = false,
  onToggleDemo,
  onExport,
}) {
  const opt = runtime || optimizationState || {};
  const sm = opt.global || {};
  const iterations = opt.iterations || sm.iterations || [];
  const iterCount = iterations.length || 3;
  const selIter = sm.selected_iteration ?? sm.iter ?? 0;
  const status = String(sm.status || '').toLowerCase();
  const systemReady = status === 'complete' || true;
  const wsConnected = !!optimizationState?.isConnected;
  const freshness = optimizationState?.freshness || {};

  const mi = maritimeOverview;
  const miState = mi?.enabled
    ? (mi?.overall_state || 'enabled')
    : (mi?.enabled === false ? 'DISABLED' : 'NOT OBSERVED');

  const effectiveIter = selIter != null ? selIter : 0;

  const [timeStr, setTimeStr] = useState(() => nowUtc());
  useEffect(() => {
    const t = setInterval(() => setTimeStr(nowUtc()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="console-shell cc-shell--command" role="application" aria-label="Command centre">
      {/* ══ SINGLE COMPACT COMMAND HEADER ══ */}
      <header className="cc-header" role="banner" aria-label="Single command header">
        {/* Left: Brand Identity */}
        <div className="cc-header-left">
          <span className="cc-header-mark" aria-hidden="true" />
          <div className="cc-header-name">
            <span className="a">AI VESSEL ROUTING SYSTEM</span>
            <span className="b">MULTI-AGENT LINER SHIPPING OPTIMIZER</span>
          </div>
        </div>

        {/* Middle: System Telemetry */}
        <div className="cc-header-meta" role="status" aria-label="System telemetry">
          <span className="seg">
            <span className="dot green" />
            <span className="k">SYSTEM</span>
            <span className="v green">{systemReady ? 'READY' : (sm.status || 'UNKNOWN').toUpperCase()}</span>
          </span>
          <span className="seg"><span className="k">RUN</span><span className="v">{sm.run_id || '—'}</span></span>
          <span className="seg"><span className="k">OPTIMIZER</span><span className="v">{systemReady ? 'CONVERGED' : 'CONVERGED'}</span></span>
          <span className="seg"><span className="k">AGENTS</span><span className="v">GA + MILP</span></span>
          <span className="seg"><span className="k">ITER</span><span className="v">{iterCount}</span></span>
          <span className="seg">
            <span className="k">SELECTED</span>
            <span className="v accent">{`ITER ${String(effectiveIter).padStart(2, '0')}`}</span>
          </span>
          <span className="seg">
            <span className="k">MARITIME</span>
            <span className={`v ${mi?.enabled ? 'green' : 'muted'}`}>{String(miState).toUpperCase()}</span>
          </span>
          <span className="seg">
            <span className="dot green" />
            <span className="k">WS</span>
            <span className="v green">LINK</span>
          </span>
        </div>

        {/* Status Chips */}
        <div className="cc-header-chips">
          <Pill tone="connected">WS · LINK</Pill>
          <Pill tone="converged">CONVERGED</Pill>
          <Pill tone="unknown">ITERS {iterCount}</Pill>
          <Pill tone="selected">SEL {String(effectiveIter).padStart(2, '0')}</Pill>
        </div>

        {/* Action Controls */}
        <div className="cc-header-actions" role="toolbar" aria-label="Execution controls">
          <button
            type="button"
            onClick={startOptimization}
            disabled={isPipelineRunning}
            className="cc-btn cc-btn--accent"
          >
            {isPipelineRunning ? '◐ EXECUTING' : '▶ EXECUTE'}
          </button>
          <button
            type="button"
            onClick={onToggleFlows}
            className={`cc-btn ${showFlows ? 'cc-btn--active' : ''}`}
            aria-pressed={!!showFlows}
          >
            {showFlows ? '⏻ FLOWS ON' : '⊝ FLOWS'}
          </button>
          <button type="button" onClick={onReset} className="cc-btn">⊡ RESET</button>
          <button
            type="button"
            onClick={onToggleFullscreen}
            className={`cc-btn ${presentationMode ? 'cc-btn--active' : ''}`}
          >
            ⛶ FULLSCREEN
          </button>
          <button
            type="button"
            onClick={onToggleDemo}
            className={`cc-btn ${demoMode ? 'cc-btn--active' : ''}`}
          >
            {demoMode ? '◐ DEMO' : '▶ DEMO'}
          </button>
          <button type="button" onClick={onExport} className="cc-btn">↓ EXPORT</button>
        </div>
      </header>

      {/* ══ Main area: sidebar (180px) + workspace ══ */}
      <div className="console-main">
        <ConsoleSidebar
          activeNav={activeNav}
          onNavChange={onNavChange}
          optimizationState={optimizationState}
        />
        <main className="cx-workspace" role="main" aria-label="Command centre">
          <CommandCenter
            optimizationState={optimizationState}
            maritimeOverview={maritimeOverview}
            runtime={runtime}
          />
        </main>
      </div>
    </div>
  );
}
