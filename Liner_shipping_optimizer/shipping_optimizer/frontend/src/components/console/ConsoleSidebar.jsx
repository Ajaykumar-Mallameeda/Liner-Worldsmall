/**
 * ConsoleSidebar
 * --------------
 * Terminal-style navigation rail: one item per navigation group (navItems.navGroups).
 * Active group shown via a thin cyan rail + cyan text + faint gradient.
 *
 * Responsive: full rail >= 1280 px, icon rail 768-1279 px, off-canvas drawer < 768 px
 * (opened from the header's menu button; `open` / `onClose` control it).
 *
 * Pure presentational. Counts + state come from props.
 *
 * Motion: one marker (rail + tint) glides between items instead of each item lighting up on its own; hovering
 * or focusing an item preloads that group's tab code. Keys 1–8 open the groups (MaritimeDashboard).
 */

import { useRef } from 'react';
import { navGroups, groupOfTab } from '../layout/navItems.js';
import { fmtNum } from '../../utils/formatters.js';
import { Pill, State } from './p12.jsx';
import { liveLinkOf } from '../../runtime/consoleSelectors.js';
import { preloadTab } from '../../views/console/tabLoaders.js';
import useGlide from './useGlide.js';

export default function ConsoleSidebar({ activeNav, onNavChange, optimizationState, counts = {}, lastTabByGroup = {}, open = false, onClose }) {
  const activeGroup = groupOfTab(activeNav).id;
  const navRef = useRef(null);
  const glide = useGlide(navRef, activeGroup);

  const sc = optimizationState?.global?.test_scorecard || {};
  const passed = sc.assertions_passed;
  const total = sc.assertions_total;
  const warnings = sc.warnings;
  const score = sc.score;
  const scorePct =
    score != null ? score :
    passed != null && total ? (passed / total) * 100 : null;
  const link = liveLinkOf(optimizationState);
  const running = !!optimizationState?.isPipelineRunning;

  const go = (g) => {
    onNavChange(lastTabByGroup[g.id] || g.tabs[0].id);
    if (onClose) onClose();
  };

  return (
    <>
      <div className={`cx-drawer-scrim ${open ? 'is-open' : ''}`} onClick={onClose} aria-hidden="true" />
      <aside id="console-nav" className={`cx-sidebar ${open ? 'is-open' : ''}`} role="navigation" aria-label="Console navigation">
        <div className="rail-head">
          <div className="eyebrow">Console</div>
          <div className="title">Vessel Routing</div>
        </div>

        <nav className="nav-scroll has-glide" aria-label="Primary" ref={navRef}>
          {glide && (
            <span className="nav-glide" aria-hidden="true" style={{ transform: `translateY(${glide.y}px)`, height: glide.h }} />
          )}
          {navGroups.map((g, i) => {
            const active = activeGroup === g.id;
            const count = counts[g.id];
            const target = lastTabByGroup[g.id] || g.tabs[0].id;
            return (
              <button
                key={g.id}
                type="button"
                onClick={() => go(g)}
                onPointerEnter={() => preloadTab(target)}
                onFocus={() => preloadTab(target)}
                className={`nav-item ${active ? 'is-active' : ''}`}
                aria-current={active ? 'page' : undefined}
                aria-keyshortcuts={String(i + 1)}
                title={`${g.tabs.length > 1 ? `${g.label}: ${g.tabs.map((t) => t.label).join(', ')}` : g.label} · key ${i + 1}`}
              >
                <span className="icon" aria-hidden="true">{g.icon}</span>
                <span className="label">{g.label}</span>
                {count != null && <span className="count">{fmtNum(count)}</span>}
                {count == null && g.tabs.length > 1 && <span className="count" aria-hidden="true">{g.tabs.length}</span>}
              </button>
            );
          })}
        </nav>

        <div className="rail-foot">
          <div className="rail-foot-link" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <State tone={link.tone === 'ok' ? 'connected' : link.tone === 'warn' ? 'warn' : 'unknown'} label={link.label} />
            {running && (
              <span style={{ marginLeft: 'auto' }}>
                <Pill tone="active">{optimizationState?.currentStage || 'running'}</Pill>
              </span>
            )}
          </div>
          {(passed != null || scorePct != null || warnings != null) && (
            <>
              <div className="row">
                <span className="k">assertions</span>
                <span className={`v ${passed != null && total && passed / total > 0.95 ? 'good' : 'warn'}`}>
                  {passed != null ? `${passed}/${total ?? '—'}` : '—'}
                </span>
              </div>
              <div className="row">
                <span className="k">score</span>
                <span className={`v ${scorePct !== null && Number(scorePct) >= 95 ? 'good' : scorePct >= 80 ? 'warn' : 'bad'}`}>
                  {scorePct != null ? `${Number(scorePct).toFixed(1)}%` : '—'}
                </span>
              </div>
              <div className="row">
                <span className="k">warnings</span>
                <span className={`v ${(warnings || 0) > 0 ? 'warn' : 'good'}`}>{warnings != null ? warnings : '—'}</span>
              </div>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
