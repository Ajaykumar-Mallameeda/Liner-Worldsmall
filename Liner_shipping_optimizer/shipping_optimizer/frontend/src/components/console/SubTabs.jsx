/**
 * SubTabs
 * -------
 * Tab strip for a navigation group with more than one tab (e.g. Optimization: Decision, Pipeline ...).
 * Arrow keys move between tabs (WAI-ARIA tabs pattern, automatic activation); [ and ] work from anywhere.
 *
 * Motion: the underline glides to the chosen tab (transform only); it jumps without gliding when the group
 * changes. Hovering or focusing a tab preloads its code.
 */

import { useRef } from 'react';
import useGlide from './useGlide.js';
import { preloadTab } from '../../views/console/tabLoaders.js';

const BASE = 100;   // the underline is BASE px wide and scaled to the tab's width

export default function SubTabs({ group, activeTab, onSelect }) {
  const refs = useRef([]);
  const listRef = useRef(null);
  const glide = useGlide(listRef, `${group?.id}:${activeTab}`);
  // Glide only between tabs of the same group: the marker is keyed by group and hidden until it has been
  // measured in this group, so a group change mounts it in place instead of sliding across.
  const glideHere = glide && String(glide.key).split(':')[0] === group?.id;

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
    <div className="cx-subtabs" role="tablist" aria-label={`${group.label} sections`} onKeyDown={onKeyDown} ref={listRef}>
      <span className="cx-subtabs-group" aria-hidden="true" title="[ and ] step through these tabs">{group.label}</span>
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
            onPointerEnter={() => preloadTab(t.id)}
            onFocus={() => preloadTab(t.id)}
          >
            {t.label}
          </button>
        );
      })}
      {glideHere && (
        <span
          key={group.id}
          className="cx-subtab-glide"
          aria-hidden="true"
          style={{ transform: `translateX(${glide.x + 10}px) scaleX(${Math.max(0, glide.w - 20) / BASE})` }}
        />
      )}
    </div>
  );
}
