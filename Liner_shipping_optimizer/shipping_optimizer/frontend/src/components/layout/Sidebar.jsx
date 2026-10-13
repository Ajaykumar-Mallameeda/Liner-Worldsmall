/**
 * Sidebar — Phase 12
 * ------------------
 * Terminal navigation rail. Grouped by IA section, with
 * counts, active rail, and a state footer pulled from real
 * runtime data. Visually inspired by Crucix: hairline borders,
 * mono caps, glow-rail active state, no rounded cards.
 *
 * The `counts` and `state` props come from the parent (App) so
 * the sidebar stays purely presentational.
 */

import navItems from './navItems.js';
import { fmtNum } from '../../utils/formatters.js';
import { Pill, State, Dot } from '../console/p12.jsx';

export default function Sidebar({ activeNav, onNavChange, optimizationState, counts = {} }) {
  // Phase 12 - group nav items by section so the sidebar reads
  // as an operational console: COMMAND / INTELLIGENCE /
  // AI OPERATIONS / SYSTEM.
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
    score != null
      ? score
      : passed != null && total
      ? (passed / total) * 100
      : null;

  const isConnected = !!optimizationState?.isConnected;
  const running = !!optimizationState?.isPipelineRunning;

  return (
    <aside
      className="p12-sidebar dashboard-sidebar"
      style={{ width: 240 }}
      role="navigation"
      aria-label="Console navigation"
    >
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
                  <span className="label" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
                  {count != null && <span className="count">{fmtNum(count)}</span>}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="rail-foot">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
          <State tone={isConnected ? 'connected' : 'offline'} label={isConnected ? 'WS · LINK' : 'WS · OFFLINE'} />
          {running && (
            <span style={{ marginLeft: 'auto' }}>
              <Pill tone="active" dot>
                {optimizationState?.currentStage || 'running'}
              </Pill>
            </span>
          )}
        </div>
        <KvMicro k="assertions" v={passed != null ? `${passed}/${total ?? '—'}` : '—'} tone={passed != null && total && passed / total > 0.95 ? 'good' : 'warn'} />
        <KvMicro k="score" v={scorePct != null ? `${Number(scorePct).toFixed(1)}%` : '—'} tone={scorePct !== null && Number(scorePct) >= 95 ? 'good' : scorePct >= 80 ? 'warn' : 'bad'} />
        <KvMicro k="warnings" v={warnings != null ? `${warnings}` : '0'} tone={(warnings || 0) > 0 ? 'warn' : 'good'} />
      </div>
    </aside>
  );
}

function KvMicro({ k, v, tone }) {
  const color =
    tone === 'good' ? 'var(--p12-green)' :
    tone === 'warn' ? 'var(--p12-amber)' :
    tone === 'bad'  ? 'var(--p12-red)'   :
                      'var(--p12-ink)';
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr auto',
      alignItems: 'baseline',
      gap: 8,
      padding: '4px 0',
      borderTop: '1px solid var(--p12-divider)',
    }}>
      <span className="p12-meta">{k}</span>
      <span className="p12-data" style={{ color, fontWeight: 600 }}>{v}</span>
    </div>
  );
}
