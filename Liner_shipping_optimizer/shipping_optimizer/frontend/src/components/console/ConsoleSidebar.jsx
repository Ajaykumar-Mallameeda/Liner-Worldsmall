/**
 * ConsoleSidebar
 * --------------
 * Terminal-style navigation rail. Grouped by IA section; active
 * item shown via a thin cyan rail + cyan text + faint gradient.
 * No pill-shaped nav buttons. Compact dimensions.
 *
 * Pure presentational. Counts + state come from props.
 */

import navItems from '../layout/navItems.js';
import { fmtNum } from '../../utils/formatters.js';
import { Pill, State } from './p12.jsx';

export default function ConsoleSidebar({ activeNav, onNavChange, optimizationState, counts = {} }) {
  const sections = [];
  navItems.forEach((item) => {
    const last = sections[sections.length - 1];
    if (!last || last.name !== item.section) {
      sections.push({ name: item.section, items: [item] });
    } else {
      last.items.push(item);
    }
  });

  const sc = optimizationState?.global?.test_scorecard || {};
  const passed = sc.assertions_passed;
  const total = sc.assertions_total;
  const warnings = sc.warnings;
  const score = sc.score;
  const scorePct =
    score != null ? score :
    passed != null && total ? (passed / total) * 100 : null;
  const isConnected = !!optimizationState?.isConnected;
  const running = !!optimizationState?.isPipelineRunning;

  return (
    <aside className="cx-sidebar" role="navigation" aria-label="Console navigation">
      <div className="rail-head">
        <div className="eyebrow">Console Nav</div>
        <div className="title">Vessel Routing</div>
      </div>

      <nav className="nav-scroll" aria-label="Primary">
        {sections.map((sec) => (
          <div key={sec.name}>
            <div className="nav-section">{sec.name}</div>
            {sec.items.map(({ id, label, icon }) => {
              const active = activeNav === id;
              const count = counts[id];
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => onNavChange(id)}
                  className={`nav-item ${active ? 'is-active' : ''}`}
                  aria-current={active ? 'page' : undefined}
                >
                  <span className="icon" aria-hidden="true">{icon}</span>
                  <span className="label">{label}</span>
                  {count != null && <span className="count">{fmtNum(count)}</span>}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="rail-foot">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <State tone={isConnected ? 'connected' : 'offline'} label={isConnected ? 'WS · LINK' : 'WS · OFFLINE'} />
          {running && (
            <span style={{ marginLeft: 'auto' }}>
              <Pill tone="active">{optimizationState?.currentStage || 'running'}</Pill>
            </span>
          )}
        </div>
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
          <span className={`v ${(warnings || 0) > 0 ? 'warn' : 'good'}`}>{warnings != null ? warnings : '0'}</span>
        </div>
      </div>
    </aside>
  );
}
