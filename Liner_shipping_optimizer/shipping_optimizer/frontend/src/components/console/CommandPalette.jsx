/**
 * CommandPalette — Ctrl+K / ⌘K (or the header Search button, or "/" outside a text field).
 * Jumps to any tab, opens a service or a port on the Network tab, sets or clears the agent cross-filter,
 * and switches theme, density and compare mode. Everything listed comes from the run on screen.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import navItems from '../layout/navItems.js';
import { fmtUsd } from '../../utils/formatters.js';
import { getPortFullLabel } from '../../utils/portLookup.js';
import { requestPort, requestService, setAgentFocus, useAgentFocus } from '../../services/focusStore.js';
import { toggleDensity, toggleTheme, usePrefs } from '../../services/prefsStore.js';

export const openPalette = () => window.dispatchEvent(new Event('vr:palette'));

/** Shortest stretch of t, starting at a match of q[0], that contains q's letters in order (Infinity if none). */
function tightestSpan(t, q) {
  let best = Infinity;
  for (let s = t.indexOf(q[0]); s >= 0; s = t.indexOf(q[0], s + 1)) {
    let j = 1; let k = s + 1;
    for (; k < t.length && j < q.length; k++) if (t[k] === q[j]) j++;
    if (j === q.length) best = Math.min(best, k - s);
  }
  return best;
}

function score(text, q) {
  const t = text.toLowerCase();
  const i = t.indexOf(q);
  if (i === 0) return 3;
  if (i > 0) return t[i - 1] === ' ' || t[i - 1] === '›' || t[i - 1] === '(' ? 2.5 : 2;
  // Loose match: the letters in order within a short stretch ("dbrv" finds "DEBRV"), not scattered over a sentence.
  return q.length > 1 && tightestSpan(t, q) <= q.length * 2 ? 1 : 0;
}

export default function CommandPalette({ runtime, onNavigate }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [active, setActive] = useState(0);
  const [agent] = useAgentFocus();
  const prefs = usePrefs();
  const input = useRef(null);
  const list = useRef(null);
  const lastFocus = useRef(null);

  useEffect(() => {
    const onKey = (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target?.tagName || '') || e.target?.isContentEditable;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setOpen((v) => !v); }
      else if (e.key === '/' && !typing) { e.preventDefault(); setOpen(true); }
    };
    const onOpen = () => setOpen(true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('vr:palette', onOpen);
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('vr:palette', onOpen); };
  }, []);

  useEffect(() => {
    if (open) {
      lastFocus.current = document.activeElement;
      setQ(''); setActive(0);
      setTimeout(() => input.current?.focus(), 0);
    } else if (lastFocus.current && lastFocus.current.focus) {
      lastFocus.current.focus();
    }
  }, [open]);

  const items = useMemo(() => {
    const out = [];
    navItems.forEach((n) => out.push({ group: 'Go to', label: `${n.section} › ${n.label}`, run: () => onNavigate(n.id) }));
    const regions = Object.values(runtime?.regions || {});
    if (agent) out.push({ group: 'Filter', label: `Clear agent filter (${agent})`, run: () => setAgentFocus(null) });
    regions.forEach((r) => {
      const a = r.region || r.name;
      if (a && a !== agent) out.push({ group: 'Filter', label: `Filter every view to the ${r.name || a} agent`, hint: r.coverage != null ? `${Number(r.coverage).toFixed(1)}% coverage` : '', run: () => setAgentFocus(a) });
    });
    out.push({ group: 'View', label: 'Compare iterations and the 30-seed mean', run: () => { onNavigate('command_center'); setTimeout(() => window.dispatchEvent(new Event('vr:compare')), 50); } });
    out.push({ group: 'View', label: `Switch to ${prefs.theme === 'dark' ? 'light' : 'dark'} theme`, run: toggleTheme });
    out.push({ group: 'View', label: `Switch to ${prefs.density === 'compact' ? 'comfortable' : 'compact'} density`, run: toggleDensity });
    const services = runtime?.global?.selected_services || [];
    const ports = new Map();
    services.forEach((s) => {
      out.push({ group: 'Service', label: `Service ${s.id}`, hint: `${fmtUsd(s.weekly_profit)}/wk · ${(s.ports || []).length} calls · ${s.agent_region || s.region || ''}`, run: () => { onNavigate('network_intel'); requestService(s.id); } });
      (s.ports || []).forEach((p) => ports.set(p, (ports.get(p) || 0) + 1));
    });
    [...ports.entries()].sort((a, b) => b[1] - a[1]).forEach(([p, n]) => {
      out.push({ group: 'Port', label: `Port ${getPortFullLabel(p) || p}`, hint: `${n} call${n > 1 ? 's' : ''} in plan`, run: () => { onNavigate('network_intel'); requestPort(p); } });
    });
    return out;
  }, [runtime, agent, prefs, onNavigate]);

  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return items.filter((it) => it.group !== 'Service' && it.group !== 'Port').concat(items.filter((it) => it.group === 'Service').slice(0, 5));
    return items.map((it) => ({ it, sc: score(`${it.label} ${it.hint || ''}`, s) }))
      .filter((x) => x.sc > 0).sort((a, b) => b.sc - a.sc).slice(0, 60).map((x) => x.it);
  }, [items, q]);

  useEffect(() => { setActive(0); }, [q]);
  useEffect(() => {
    list.current?.querySelector(`[data-idx="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  if (!open) return null;
  const choose = (it) => { setOpen(false); it.run(); };
  const onKeyDown = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); setOpen(false); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(results.length - 1, a + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === 'Enter' && results[active]) { e.preventDefault(); choose(results[active]); }
    else if (e.key === 'Tab') e.preventDefault(); // keep focus in the dialog
  };

  let lastGroup = null;
  return (
    <div className="cmdk-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
      <div className="cmdk" role="dialog" aria-modal="true" aria-label="Command palette" onKeyDown={onKeyDown}>
        <input
          ref={input}
          className="cmdk-input"
          placeholder="Jump to a tab, service, port or agent…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          role="combobox"
          aria-expanded="true"
          aria-controls="cmdk-list"
          aria-activedescendant={results[active] ? `cmdk-${active}` : undefined}
        />
        <div className="cmdk-list" id="cmdk-list" role="listbox" ref={list}>
          {results.length === 0 && <div className="cmdk-empty">Nothing matches “{q}”.</div>}
          {results.map((it, i) => {
            const head = it.group !== lastGroup ? it.group : null;
            lastGroup = it.group;
            return (
              <React.Fragment key={`${it.group}-${it.label}`}>
                {head && <div className="cmdk-group" aria-hidden="true">{head}</div>}
                <div
                  id={`cmdk-${i}`}
                  data-idx={i}
                  role="option"
                  aria-selected={i === active}
                  className={`cmdk-item ${i === active ? 'is-active' : ''}`}
                  onMouseMove={() => setActive(i)}
                  onClick={() => choose(it)}
                >
                  <span className="l">{it.label}</span>
                  {it.hint && <span className="h">{it.hint}</span>}
                </div>
              </React.Fragment>
            );
          })}
        </div>
        <div className="cmdk-foot"><span>↑↓ move</span><span>Enter open</span><span>Esc close</span></div>
      </div>
    </div>
  );
}
