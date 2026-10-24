/**
 * TopHeaderBar.jsx
 * ----------------
 * Unified, persistent top status header for ALL dashboard pages.
 * Displays:
 * 1. Brand identity
 * 2. Run picker (latest local run or a frozen benchmark seed)
 * 3. Results file time from the server's Last-Modified header (never a placeholder)
 * 4. Run outcome and selected iteration, read from the run itself
 * 5. Live pipeline link state (the one WebSocket status every panel shares)
 * 6. IST clock
 */

import React, { useState, useEffect } from 'react';
import RunPicker from './RunPicker.jsx';
import { selectedIterationOf, liveLinkOf } from '../../runtime/consoleSelectors.js';
import { openPalette } from './CommandPalette.jsx';
import LogoMark from '../common/LogoMark.jsx';
import { useAgentFocus } from '../../services/focusStore.js';
import { toggleDensity, toggleTheme, usePrefs } from '../../services/prefsStore.js';

function getISTFormatted() {
  try {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(new Date()) + ' IST';
  } catch (_) {
    return new Date().toLocaleTimeString() + ' IST';
  }
}

function fmtUtc(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
}

export default function TopHeaderBar({ optimizationState, runtime, navOpen = false, onToggleNav }) {
  const [istTime, setIstTime] = useState(() => getISTFormatted());

  useEffect(() => {
    const timer = setInterval(() => setIstTime(getISTFormatted()), 1000);
    return () => clearInterval(timer);
  }, []);

  const opt = runtime || optimizationState || {};
  const g = opt.global || {};
  const source = opt.source || optimizationState?.source || null;
  const loaded = Boolean(g.selected_services && g.selected_services.length) || g.weeklyProfit != null;

  const fileTime = fmtUtc(source?.modifiedIso || g.evaluated_at);
  const outcome = String(g.health_status?.status || g.status || '').toLowerCase();
  const outcomeLabel = !loaded ? 'no results' : (outcome === 'completed' || outcome === 'complete') ? 'completed' : (outcome || 'unknown');
  const selIter = selectedIterationOf(opt);
  const servicesCount = g.selected_services?.length ?? null;
  const link = liveLinkOf(optimizationState);
  const [agent, setAgent] = useAgentFocus();
  const prefs = usePrefs();
  const isMac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform || '');

  return (
    <header className="cx-top-header" role="banner" aria-label="System status header">
      <div className="cx-top-header-left">
        {onToggleNav && (
          <button
            type="button"
            className="cx-nav-toggle"
            onClick={onToggleNav}
            aria-expanded={navOpen}
            aria-controls="console-nav"
            aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
          >
            <span aria-hidden="true">{navOpen ? '✕' : '☰'}</span>
          </button>
        )}
        <LogoMark size={18} />
        <div className="cx-top-header-title">
          <span className="name">AI Vessel Routing</span>
          <span className="tag">Multi-agent optimizer</span>
        </div>
      </div>

      <div className="cx-top-header-center">
        <RunPicker />

        <div className="cx-th-pill" title="Modification time of the results file being shown">
          <span className={`cx-th-status-dot ${loaded ? 'online' : 'offline'}`} aria-hidden="true" />
          <span className="k">Results</span>
          <span className="v">{loaded ? (fileTime || 'time unknown') : 'not loaded'}</span>
        </div>

        <div className="cx-th-pill cx-th-pill--secondary">
          <span className="k">Outcome</span>
          <span className={`v ${outcomeLabel === 'completed' ? 'green' : 'amber'}`}>{outcomeLabel}</span>
          {selIter != null && (
            <>
              <span className="v-sep">·</span>
              <span className="k">Selected</span>
              <span className="v accent">iter {String(selIter).padStart(2, '0')}</span>
            </>
          )}
          {servicesCount != null && <span className="tag-sub">{servicesCount} services</span>}
        </div>
      </div>

      <div className="cx-top-header-right">
        {agent && (
          <span className="cx-th-chip" title="Every view is filtered to this regional agent's services">
            <span className="k">Agent</span> {agent}
            <button type="button" onClick={() => setAgent(null)} aria-label={`Clear the ${agent} agent filter`}>✕</button>
          </span>
        )}
        <button type="button" className="cx-th-search" onClick={openPalette} aria-label="Search and jump (Ctrl+K)" title="Search tabs, services, ports and agents">
          <span aria-hidden="true">⌕</span><span className="lbl">Search</span><kbd>{isMac ? '⌘K' : 'Ctrl K'}</kbd>
        </button>
        <button type="button" className="cx-th-icon" onClick={toggleTheme} aria-label={`Switch to ${prefs.theme === 'dark' ? 'light' : 'dark'} theme`} title={`Theme: ${prefs.theme}`}>
          <span aria-hidden="true">{prefs.theme === 'dark' ? '☾' : '☀'}</span>
        </button>
        <button type="button" className="cx-th-icon" onClick={toggleDensity} aria-label={`Switch to ${prefs.density === 'compact' ? 'comfortable' : 'compact'} density`} title={`Density: ${prefs.density}`}>
          <span aria-hidden="true">{prefs.density === 'compact' ? '☷' : '☰'}</span>
        </button>
        <span className={`cx-th-ws-badge is-${link.tone}`} title={link.title}>
          <span className="dot" aria-hidden="true" />
          {link.label}
        </span>
        <span className="cx-th-clock">{istTime}</span>
      </div>
    </header>
  );
}
