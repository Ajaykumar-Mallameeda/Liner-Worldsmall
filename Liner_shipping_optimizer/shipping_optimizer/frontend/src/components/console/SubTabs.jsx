/**
 * SubTabs
 * -------
 * Tab strip for a navigation group with more than one tab (e.g. Optimization: Decision, Pipeline ...).
 * Arrow keys move between tabs (WAI-ARIA tabs pattern, automatic activation).
 */

import { useRef } from 'react';

export default function SubTabs({ group, activeTab, onSelect }) {
  const refs = useRef([]);
  if (!group || group.tabs.length < 2) return null;
  const idx = Math.max(0, group.tabs.findIndex((t) => t.id === activeTab));

  const onKeyDown = (e) => {
    let next = null;
    if (e.key === 'ArrowRight') next = (idx + 1) % group.tabs.length;
    if (e.key === 'ArrowLeft') next = (idx - 1 + group.tabs.length) % group.tabs.length;
    if (e.key === 'Home') next = 0;
    if (e.key === 'End') next = group.tabs.length - 1;
    if (next == null) return;
    e.preventDefault();
    onSelect(group.tabs[next].id);
    refs.current[next]?.focus();
  };

  return (
    <div className="cx-subtabs" role="tablist" aria-label={`${group.label} sections`} onKeyDown={onKeyDown}>
      <span className="cx-subtabs-group" aria-hidden="true">{group.label}</span>
      {group.tabs.map((t, i) => {
        const active = t.id === activeTab;
        return (
          <button
            key={t.id}
            ref={(el) => { refs.current[i] = el; }}
            type="button"
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            className={`cx-subtab ${active ? 'is-active' : ''}`}
            onClick={() => onSelect(t.id)}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
