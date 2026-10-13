/**
 * p12-primitives
 * --------------
 * Phase 12 — the shared visual primitives used by every page
 * of the command console. These are the atoms of the new
 * design system. Pure presentational; they never reach
 * outside their own subtree and never read runtime state.
 *
 * Conventions:
 *   - The `tone` prop maps to the state vocabulary:
 *     live | connected | available | active | selected | converged
 *     warn | degraded | stale | error | crit | offline | down
 *     disabled | unknown | no_data | not_observed | synthetic
 *   - `tone` is also accepted as `state` for symmetry.
 *   - Every primitive honors `prefers-reduced-motion`.
 */

import { memo, useEffect, useMemo, useState } from 'react';

/* === 1. Dot ================================================== */
function normalizeTone(t) {
  if (!t) return 'unknown';
  return String(t).toLowerCase().replace(/[\s-]+/g, '_');
}
const TONE_TO_PILL = {
  live:           'p12-dot--live',
  connected:      'p12-dot--connected',
  available:      'p12-dot--available',
  active:         'p12-dot--active',
  selected:       'p12-dot--selected',
  converged:      'p12-dot--converged',
  warn:           'p12-dot--warn',
  degraded:       'p12-dot--degraded',
  stale:          'p12-dot--stale',
  error:          'p12-dot--error',
  crit:           'p12-dot--crit',
  failed:         'p12-dot--error',
  down:           'p12-dot--down',
  offline:        'p12-dot--offline',
  disabled:       'p12-dot--disabled',
  unknown:        'p12-dot--unknown',
  no_data:        'p12-dot--no_data',
  not_observed:   'p12-dot--not_observed',
  synthetic:      'p12-dot--synthetic',
};

export function Dot({ tone = 'unknown', pulse = false, size, className = '', style, title }) {
  const t = normalizeTone(tone);
  const cls = TONE_TO_PILL[t] || 'p12-dot--unknown';
  const dim = size ? { width: size, height: size } : undefined;
  return (
    <span
      className={`p12-dot ${cls} ${pulse ? 'p12-dot--pulse' : ''} ${className}`}
      style={{ ...dim, ...style }}
      role="presentation"
      aria-hidden="true"
      title={title || t}
    />
  );
}

/* === 2. Pill (chip with state) ============================== */
const PILL_CLASS = {
  live:           'p12-pill--live',
  connected:      'p12-pill--connected',
  available:      'p12-pill--available',
  active:         'p12-pill--active',
  selected:       'p12-pill--selected',
  converged:      'p12-pill--converged',
  warn:           'p12-pill--warn',
  degraded:       'p12-pill--degraded',
  stale:          'p12-pill--stale',
  error:          'p12-pill--error',
  crit:           'p12-pill--crit',
  failed:         'p12-pill--error',
  down:           'p12-pill--error',
  offline:        'p12-pill--offline',
  disabled:       'p12-pill--disabled',
  unknown:        'p12-pill--unknown',
  no_data:        'p12-pill--no_data',
  not_observed:   'p12-pill--not_observed',
  synthetic:      'p12-pill--synthetic',
};

export function Pill({ tone = 'unknown', children, className = '', dot = true, ...rest }) {
  const t = normalizeTone(tone);
  const cls = PILL_CLASS[t] || 'p12-pill--unknown';
  return (
    <span
      className={`p12-pill ${cls} ${className}`}
      role="status"
      aria-label={`${t}${children ? `: ${children}` : ''}`}
      {...rest}
    >
      {dot && <Dot tone={t} />}
      <span>{children || t.toUpperCase()}</span>
    </span>
  );
}

/* === 3. State — longer inline label with mark ================ */
const STATE_CLASS = {
  live:           'p12-state--live',
  connected:      'p12-state--connected',
  available:      'p12-state--available',
  active:         'p12-state--active',
  selected:       'p12-state--selected',
  converged:      'p12-state--converged',
  warn:           'p12-state--warn',
  degraded:       'p12-state--degraded',
  stale:          'p12-state--stale',
  error:          'p12-state--error',
  crit:           'p12-state--crit',
  failed:         'p12-state--error',
  down:           'p12-state--error',
  offline:        'p12-state--offline',
  disabled:       'p12-state--disabled',
  unknown:        'p12-state--unknown',
  no_data:        'p12-state--no_data',
  not_observed:   'p12-state--not_observed',
  synthetic:      'p12-state--synthetic',
};

export function State({ tone = 'unknown', label, prefix }) {
  const t = normalizeTone(tone);
  const cls = STATE_CLASS[t] || 'p12-state--unknown';
  const text = label || t.toUpperCase().replace(/_/g, ' ');
  return (
    <span className={`p12-state ${cls}`} role="status" aria-label={text}>
      {prefix && <span style={{ color: 'var(--p12-ink-faint)' }}>{prefix}</span>}
      <span className="mark" aria-hidden="true" />
      <span>{text}</span>
    </span>
  );
}

/* === 4. Key/Value cell ====================================== */
export function Kv({ k, v, tone, head = false, tight = false, loose = false, className = '' }) {
  const toneCls = tone ? `v--${tone}` : '';
  return (
    <div
      className={`p12-kv ${head ? 'p12-kv--head' : ''} ${tight ? 'p12-kv--tight' : ''} ${loose ? 'p12-kv--loose' : ''} ${className}`}
    >
      <span className="k">{k}</span>
      <span className={`v ${toneCls}`}>{v ?? '—'}</span>
    </div>
  );
}

/* === 5. Stat tile (numeric headline) ========================= */
const STAT_VARIANT = {
  accent: 'p12-stat--accent',
  good:   'p12-stat--good',
  warn:   'p12-stat--warn',
  bad:    'p12-stat--bad',
  purple: 'p12-stat--purple',
  muted:  'p12-stat--muted',
};

export function Stat({ k, v, sub, variant = '', className = '' }) {
  const vCls = STAT_VARIANT[variant] || '';
  return (
    <div className={`p12-stat ${vCls} ${className}`}>
      <span className="k">{k}</span>
      <span className="v">{v ?? '—'}</span>
      {sub != null && <span className="sub">{sub}</span>}
    </div>
  );
}

/* === 6. Section (panel header + body slot) =================== */
export function Section({ title, right, children, className = '', bodyClassName = '' }) {
  return (
    <section className={`p12-surface ${className}`}>
      {(title || right) && (
        <div className="p12-section-head">
          <span className="title">{title}</span>
          {right != null && <span className="meta">{right}</span>}
        </div>
      )}
      <div className={bodyClassName} style={{ minWidth: 0 }}>
        {children}
      </div>
    </section>
  );
}

/* === 7. Empty state (typed) ================================== */
export function Empty({
  tone = 'no_data',
  label,
  title,
  hint,
  actions,
  className = '',
}) {
  const t = normalizeTone(tone);
  return (
    <div className={`p12-empty ${className}`} role="status">
      <span className="label">
        <Dot tone={t} />
        {(label || t).toUpperCase()}
      </span>
      {title && <span className="title">{title}</span>}
      {hint && <span className="hint">{hint}</span>}
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

/* === 8. Tag (typed data label) =============================== */
const TAG_VARIANT = {
  accent: 'p12-tag--accent',
  good:   'p12-tag--good',
  warn:   'p12-tag--warn',
  bad:    'p12-tag--bad',
  purple: 'p12-tag--purple',
};

export function Tag({ children, variant, className = '' }) {
  const vCls = TAG_VARIANT[variant] || '';
  return (
    <span className={`p12-tag ${vCls} ${className}`}>
      {children}
    </span>
  );
}

/* === 9. Meter (progress / proportion) ======================= */
export function Meter({ value = 0, max = 100, variant, className = '', ariaLabel }) {
  const pct = Math.max(0, Math.min(100, max > 0 ? (value / max) * 100 : 0));
  const vCls = variant ? `p12-meter--${variant}` : '';
  return (
    <div
      className={`p12-meter ${variant ? variant : ''} ${vCls} ${className}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-label={ariaLabel}
    >
      <div className="fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

/* === 10. Sparkline (compact numeric trace) =================== */
function buildPath(values, w, h) {
  if (!Array.isArray(values) || values.length === 0) return null;
  const v = values.map((n) => Number(n)).filter((n) => Number.isFinite(n));
  if (v.length === 0) return null;
  const min = Math.min(...v);
  const max = Math.max(...v);
  const range = max - min || 1;
  const stepX = v.length > 1 ? w / (v.length - 1) : w;
  const pts = v.map((y, i) => {
    const px = i * stepX;
    const py = h - ((y - min) / range) * h;
    return [px, py];
  });
  return {
    line: pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0].toFixed(2)} ${p[1].toFixed(2)}`).join(' '),
    area: `M 0 ${h} ` + pts.map((p) => `L ${p[0].toFixed(2)} ${p[1].toFixed(2)}`).join(' ') + ` L ${w} ${h} Z`,
    min, max, last: v[v.length - 1],
  };
}

export const Sparkline = memo(function Sparkline({
  values,
  width = 120,
  height = 28,
  tone,
  className = '',
  ariaLabel,
}) {
  const data = useMemo(() => buildPath(values, width, height), [values, width, height]);
  const cls = tone ? `p12-spark ${tone}` : 'p12-spark';
  if (!data) {
    return (
      <svg
        className={`${cls} empty ${className}`}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={ariaLabel || 'no data'}
      >
        <line x1="0" y1={height - 0.5} x2={width} y2={height - 0.5} stroke="currentColor" strokeWidth="0.5" opacity="0.3" />
      </svg>
    );
  }
  return (
    <svg
      className={`${cls} ${className}`}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={ariaLabel || `min ${data.min} max ${data.max} last ${data.last}`}
      preserveAspectRatio="none"
    >
      <path d={data.area} className="area" />
      <path d={data.line} />
    </svg>
  );
});

/* === 11. Drawer (context-preserving side panel) ============== */

export function Drawer({ open, onClose, eyebrow, title, footer, children }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <>
      <div className="p12-drawer-backdrop" onClick={onClose} />
      <aside className="p12-drawer" role="dialog" aria-modal="true" aria-label={typeof title === 'string' ? title : 'Detail'}>
        <header>
          <span>{eyebrow}</span>
          <span className="title">{title}</span>
          <button className="close" onClick={onClose} aria-label="Close drawer">✕ ESC</button>
        </header>
        <div className="body">{children}</div>
        {footer && <footer>{footer}</footer>}
      </aside>
    </>
  );
}

export function DrawerField({ label, value, mono = true }) {
  return (
    <div className="field">
      <span className="k">{label}</span>
      <span className="v" style={mono ? undefined : { fontFamily: 'var(--p12-font-sans)' }}>
        {value == null || value === '' ? '—' : String(value)}
      </span>
    </div>
  );
}

/* === 12. Agent Topology (multi-agent pipeline) =============== */
const NODES = [
  { id: 'data',         name: 'DATA',          sub: 'maritime snapshots',  tone: 'available' },
  { id: 'orchestrator', name: 'ORCHESTRATOR',  sub: 'pipeline entry',      tone: 'available' },
  { id: 'regionals',    name: 'REGIONAL',      sub: '×5 agents',           tone: 'available' },
  { id: 'ga',           name: 'GA',            sub: 'evolutionary',        tone: 'available' },
  { id: 'milp',         name: 'MILP',          sub: 'deterministic',       tone: 'available' },
  { id: 'validation',   name: 'VALIDATION',    sub: 'consensus · clamps',  tone: 'available' },
  { id: 'selection',    name: 'SELECTION',     sub: 'canonical pick',      tone: 'available' },
  { id: 'decision',     name: 'DECISION',      sub: 'maritime intelligence', tone: 'available' },
  { id: 'feedback',     name: 'FEEDBACK',      sub: 'next iter',           tone: 'available' },
];

const STAGE_CLASS = {
  running:     'running',
  ready:       'ready',
  idle:        'idle',
  completed:   'completed',
  degraded:    'degraded',
  unavailable: 'unavailable',
  selected:    'selected',
};

export function AgentTopology({ stateMap = {}, liveArrow = false, compact = false }) {
  return (
    <div className="p12-topology">
      {NODES.map((node, idx) => {
        const st = (stateMap && stateMap[node.id]) || 'unavailable';
        const cls = STAGE_CLASS[st] || 'unavailable';
        return (
          <div key={node.id} className="flex items-stretch">
            <div
              className={`stage ${cls}`}
              style={compact ? { minWidth: 96, padding: '6px 10px' } : undefined}
            >
              <span className="state">
                <Dot tone={st} pulse={st === 'running'} />
                {String(st).toUpperCase()}
              </span>
              <span className="name">{node.name}</span>
              <span className="sub">{node.sub}</span>
            </div>
            {idx < NODES.length - 1 && (
              <div className={`arrow ${liveArrow ? 'live' : ''}`} aria-hidden="true" />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* === 13. Decision Chain (vertical stepper) =================== */
export function DecisionChain({ steps = [], selectedId, className = '' }) {
  return (
    <ol className={`p12-chain ${className}`} role="list">
      {steps.map((s, i) => {
        const tone = String(s.tone || s.state || 'unknown');
        const cls = [
          'step',
          tone === 'ok' || tone === 'completed' || tone === 'converged' ? 'complete' : '',
          tone === 'llm' || tone === 'purple' ? 'llm' : '',
          s.id === selectedId ? 'selected' : '',
        ].filter(Boolean).join(' ');
        return (
          <li key={s.id || i} className={cls} onClick={s.onClick} role={s.onClick ? 'button' : undefined}>
            <div className="marker">
              <span className="num">{String(i + 1).padStart(2, '0')}</span>
              {i < steps.length - 1 && <span className="line" aria-hidden="true" />}
            </div>
            <div className="body">
              {s.label && <span className="label">{s.label}</span>}
              {s.name && <span className="name">{s.name}</span>}
              {s.detail && <span className="detail">{s.detail}</span>}
              {s.chips && (
                <div className="chips">
                  {s.chips.map((c, j) => (
                    <span key={j} className={`p12-tag ${c.variant ? `p12-tag--${c.variant}` : ''}`}>
                      {c.label}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/* === 13b. Iteration Ladder (vertical comparison) ============= */
export function IterationLadder({ iterations = [], selectedIter, onSelect, max = 100 }) {
  if (!Array.isArray(iterations) || iterations.length === 0) return null;
  const scoreMax = Math.max(
    0.0001,
    ...iterations.map((i) => Number(i.score || 0)),
  );
  return (
    <div className="p12-ladder">
      {iterations.map((it) => {
        const isSelected = selectedIter === it.iter;
        const score = Number(it.score || 0);
        const pct = Math.max(0, Math.min(100, (score / scoreMax) * 100));
        return (
          <div
            key={it.iter}
            className={`row ${isSelected ? 'selected' : ''}`}
            onClick={() => onSelect && onSelect(it)}
            role={onSelect ? 'button' : undefined}
            tabIndex={onSelect ? 0 : undefined}
            onKeyDown={(e) => { if (onSelect && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onSelect(it); } }}
            style={{ cursor: onSelect ? 'pointer' : 'default' }}
          >
            <span className="id">iter {String(it.iter).padStart(2, '0')}</span>
            <div className="body">
              <div className="metrics">
                <span><span className="k">score</span>&nbsp;<span className="v accent">{score ? score.toFixed(3) : '—'}</span></span>
                <span><span className="k">profit</span>&nbsp;<span className="v">{it.profit != null ? `$${Math.round(Number(it.profit)).toLocaleString()}` : '—'}</span></span>
                <span><span className="k">cov</span>&nbsp;<span className="v good">{it.coverage != null ? `${Number(it.coverage).toFixed(1)}%` : '—'}</span></span>
                <span><span className="k">runtime</span>&nbsp;<span className="v">{it.runtime_seconds != null ? `${Number(it.runtime_seconds).toFixed(1)}s` : '—'}</span></span>
                {isSelected && <Tag variant="accent">selected</Tag>}
              </div>
              <div className="bar">
                <span>convergence</span>
                <div className="track">
                  <div className="fill" style={{ width: `${pct}%` }} />
                </div>
                <span>{pct.toFixed(0)}%</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* === 14. Event Stream (typed event list) ==================== */
export function EventStream({
  events = [],
  onSelectEvent,
  selectedEventId,
  emptyTitle = 'No events observed',
  emptyHint,
  maxHeight = 360,
}) {
  if (events.length === 0) {
    return (
      <Empty
        tone="no_data"
        label="no events"
        title={emptyTitle}
        hint={emptyHint || 'The event stream is derived from real pipeline_output.json artifacts.'}
      />
    );
  }
  return (
    <div role="list" style={{ maxHeight, overflowY: 'auto' }}>
      <div className="p12-event p12-event--head" role="presentation" aria-hidden="true">
        <span className="ts">TIME</span>
        <span className="src">SOURCE</span>
        <span className="msg">EVENT</span>
        <span className="meta">TYPE</span>
        <span className="sev">SEVERITY</span>
      </div>
      {events.map((e, i) => {
        const sev = String(e.severity || 'dim').toLowerCase();
        return (
          <div
            key={e.id || i}
            role="listitem"
            className={`p12-event ${onSelectEvent ? 'clickable' : ''}`}
            style={selectedEventId === e.id ? { background: 'rgba(0, 212, 255, 0.06)' } : undefined}
            onClick={() => onSelectEvent && onSelectEvent(e)}
          >
            <span className="ts">{e.tsLabel || e.ts || '—'}</span>
            <span className="src">{e.source || 'system'}</span>
            <span className="msg">{e.summary || e.message || '—'}</span>
            <span className="meta">{e.type || ''}</span>
            <span className={`sev ${sev}`}>{(e.severity || '·').toUpperCase()}</span>
          </div>
        );
      })}
    </div>
  );
}

/* === 15. Provenance strip (footer for every view) ============ */
export function Provenance({
  source,
  sourceStatus = 'unknown',
  timestamp,
  attribution,
  license,
  recordCount,
  snapshotId,
}) {
  return (
    <div className="p12-provenance" role="contentinfo" aria-label="Provenance">
      <span><span className="k">source</span><span className="v">{source || '—'}</span></span>
      <span className="sep" aria-hidden="true" />
      <span><span className="k">state</span><span className="v"><State tone={sourceStatus} label={String(sourceStatus).toUpperCase()} /></span></span>
      {timestamp && <><span className="sep" aria-hidden="true" /><span><span className="k">last eval</span><span className="v">{timestamp}</span></span></>}
      {attribution && <><span className="sep" aria-hidden="true" /><span><span className="k">attribution</span><span className="v">{attribution}</span></span></>}
      {license && <><span className="sep" aria-hidden="true" /><span><span className="k">license</span><span className="v">{license}</span></span></>}
      {recordCount != null && <><span className="sep" aria-hidden="true" /><span><span className="k">records</span><span className="v">{Number(recordCount).toLocaleString()}</span></span></>}
      {snapshotId && <><span className="sep" aria-hidden="true" /><span><span className="k">snapshot</span><span className="v">{snapshotId}</span></span></>}
    </div>
  );
}

/* === 16. Network Intelligence Canvas (map + layers) ========== */
import WorldMap from '../map/WorldMap.jsx';

const LAYER_DEFS = [
  { id: 'ports',     label: 'PORTS',     swatch: '#00d4ff' },
  { id: 'routes',    label: 'ROUTES',    swatch: '#7c3aed' },
  { id: 'selected',  label: 'SELECTED',  swatch: '#10b981' },
  { id: 'demand',    label: 'DEMAND',    swatch: '#ffb84c' },
  { id: 'congestion',label: 'CONGEST.',  swatch: '#ff5f63' },
  { id: 'weather',   label: 'WEATHER',   swatch: '#69f0ae' },
  { id: 'vessels',   label: 'VESSELS',   swatch: '#b388ff' },
  { id: 'traffic',   label: 'TRAFFIC',   swatch: '#a78bfa' },
];

export function NetworkCanvas({
  optimizationState,
  maritimeOverview,
  hotspots = null,
  height = 460,
  defaultLayers = ['ports', 'routes', 'selected'],
}) {
  const [layers, setLayers] = useState(() => new Set(defaultLayers));

  const selectedCount = (optimizationState.global.selected_services || []).length;
  const totalProfit = optimizationState.global.weeklyProfit;
  const coverage = optimizationState.global.coverage;
  const regions = Object.values(optimizationState.regions || {});

  const hasHotspots = Array.isArray(hotspots) && hotspots.length > 0;
  const wsConnected = !!optimizationState.isConnected;

  const toggle = (id) => {
    setLayers((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  return (
    <div className="p12-canvas" style={{ height }} aria-label="Network intelligence canvas">
      <div className="legend" role="toolbar" aria-label="Map layer controls">
        <span className="label">LAYERS</span>
        {LAYER_DEFS.map((d) => {
          const active = layers.has(d.id);
          const disabled =
            (d.id === 'weather' && !maritimeOverview?.sources?.weather) ||
            (d.id === 'vessels' && !wsConnected) ||
            (d.id === 'traffic' && !maritimeOverview?.sources?.traffic) ||
            (d.id === 'congestion' && !hasHotspots);
          return (
            <button
              key={d.id}
              type="button"
              className={`item ${active ? 'on' : ''}`}
              onClick={() => !disabled && toggle(d.id)}
              aria-pressed={active}
              aria-disabled={disabled}
              title={disabled ? `${d.label}: no evidence` : d.label}
            >
              <span className="swatch" style={{ background: d.swatch }} />
              {d.label}
            </button>
          );
        })}
      </div>

      <div style={{ width: '100%', height: '100%' }}>
        <WorldMap optimizationState={optimizationState} />
      </div>

      <div className="overlay" aria-label="Canvas metrics">
        <div className="row">
          <span className="k">SELECTED</span>
          <span className="v accent">{selectedCount}</span>
          <span className="k" style={{ marginLeft: 8 }}>SERVICES</span>
        </div>
        <div className="row">
          <span className="k">WEEKLY P&amp;L</span>
          <span className="v good">
            {totalProfit > 0 ? `$${(totalProfit / 1e6).toFixed(1)}M` : '—'}
          </span>
        </div>
        <div className="row">
          <span className="k">COVERAGE</span>
          <span className="v">
            {coverage > 0 ? `${Number(coverage).toFixed(1)}%` : '—'}
          </span>
          <span className="k" style={{ marginLeft: 8 }}>REGIONS</span>
          <span className="v">{regions.length || '—'}</span>
        </div>
        {maritimeOverview && (
          <div className="row" style={{ borderTop: '1px solid var(--p12-divider)', paddingTop: 4, marginTop: 4 }}>
            <span className="k">MARITIME</span>
            <span className="v">
              {maritimeOverview.enabled
                ? (maritimeOverview.overall_state || 'enabled')
                : 'disabled'}
            </span>
          </div>
        )}
      </div>

      {selectedCount === 0 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
          <div style={{ pointerEvents: 'auto', maxWidth: 360 }}>
            <Empty
              tone="no_data"
              label="no selection"
              title="No selected network on disk"
              hint="The canvas renders ports, routes, and the selected iteration's services when an orchestrator run is on disk. When none is present, the canvas shows the world basemap only."
            />
          </div>
        </div>
      )}
    </div>
  );
}

// (end)
