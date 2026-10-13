/**
 * IdentityBar
 * -----------
 * The application's identity band: a square crest + system
 * designation + tagline, plus the global action buttons.
 *
 * Designed to read as a "technical console designation" rather
 * than a marketing logo.
 */

import { Pill } from './p12.jsx';

export default function IdentityBar({
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
  const sm = optimizationState?.global || {};
  const iterCount = (optimizationState?.iterations?.length) || 0;
  const selIter = sm.iter ?? sm.selected_iteration;
  const status = String(sm.status || '').toLowerCase();
  const optimizerTone =
    status === 'complete' ? 'converged' :
    status === 'running' ? 'active' :
    status === 'failed' ? 'error' :
    status === 'partial' ? 'degraded' :
    'unknown';

  return (
    <div className="cx-identity" role="banner" aria-label="Application identity">
      <div className="left">
        <div className="crest" aria-hidden="true">⬡</div>
        <div className="name">
          <span className="a">AI Vessel Routing System</span>
          <span className="b">Multi-Agent Liner Shipping Optimizer</span>
        </div>
        <div className="chips">
          <Pill tone={wsConnected ? 'connected' : 'offline'}>
            {wsConnected ? 'WS · LINK' : 'WS · OFFLINE'}
          </Pill>
          <Pill tone={optimizerTone}>
            {status === 'complete' ? 'CONVERGED' : (sm.status || 'UNKNOWN').toUpperCase()}
          </Pill>
          {isPipelineRunning && (
            <Pill tone="active">
              {optimizationState?.currentStage || 'running'}
            </Pill>
          )}
          {iterCount > 0 && (
            <Pill tone="available">ITERS {iterCount}</Pill>
          )}
          {selIter != null && (
            <Pill tone="selected">SEL {String(selIter).padStart(2, '0')}</Pill>
          )}
        </div>
      </div>

      <div className="actions">
        <button
          type="button"
          onClick={startOptimization}
          disabled={isPipelineRunning}
          className="cx-btn cx-btn--accent"
        >
          {isPipelineRunning ? '◐ RUNNING' : '▶ EXECUTE'}
        </button>
        <button type="button" onClick={onToggleFlows} className={`cx-btn ${showFlows ? 'cx-btn--active' : ''}`}>
          {showFlows ? '⏻ FLOWS ON' : '⊝ FLOWS OFF'}
        </button>
        <button type="button" onClick={onReset} className="cx-btn">⊡ RESET</button>
        <button
          type="button"
          onClick={onToggleFullscreen}
          className={`cx-btn ${presentationMode ? 'cx-btn--active' : ''}`}
        >
          ⛶ FULLSCREEN
        </button>
        <button
          type="button"
          onClick={onToggleDemo}
          className={`cx-btn ${demoMode ? 'cx-btn--active' : ''}`}
        >
          {demoMode ? '◐ DEMO' : '▶ DEMO'}
        </button>
        <button type="button" onClick={onExport} className="cx-btn">↓ EXPORT</button>
      </div>
    </div>
  );
}
