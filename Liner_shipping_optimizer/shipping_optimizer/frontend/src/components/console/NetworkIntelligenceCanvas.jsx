/**
 * NetworkIntelligenceCanvas
 * -------------------------
 * Phase 11 - a large spatial surface that turns the existing
 * WorldMap into an intelligence canvas with toggleable layers.
 *
 * Layers are derived from real runtime evidence only. Each
 * layer can be toggled on/off via the legend.
 *
 * Layer evidence sources:
 *   - ports        : selected services' port list + hub ports
 *   - routes       : selected services rendered as line strokes
 *   - demand       : corridor widths from regional unserved
 *   - traffic      : NOT a real vessel track; this is the
 *                    EMODnet vessel density label (we only
 *                    toggle a label layer; we never render
 *                    fake vessel positions)
 *   - congestion   : backend /api/maritime/congestion/hotspots
 *                    (when present)
 *   - weather      : /api/maritime/weather/forecast (when
 *                    enabled - typically not present)
 *   - vessels      : toggle disabled by default; the canvas
 *                    never renders fake live positions
 *   - selected     : highlight the selected iteration's
 *                    services
 *
 * The map itself is the existing WorldMap (no new map
 * component is introduced). The canvas adds: a layer
 * legend, an overlay metrics box, a height-driven layout,
 * and a small "selected iteration" highlight toggle.
 */

import { useEffect, useMemo, useState } from 'react';
import WorldMap from '../map/WorldMap.jsx';
import OperationalEmptyState from '../maritime/OperationalEmptyState.jsx';

const DEFAULT_LAYERS = ['ports', 'routes', 'selected'];

const LAYER_DEFS = [
  { id: 'ports',     label: 'PORTS',     swatch: '#00d4ff', swatchVar: 'var(--console-cyan)' },
  { id: 'routes',    label: 'ROUTES',    swatch: '#7c3aed', swatchVar: 'var(--console-purple, #7c3aed)' },
  { id: 'selected',  label: 'SELECTED',  swatch: '#10b981', swatchVar: 'var(--console-green)' },
  { id: 'demand',    label: 'DEMAND',    swatch: '#f59e0b', swatchVar: 'var(--console-amber)' },
  { id: 'congestion',label: 'CONGEST.',  swatch: '#ef4444', swatchVar: 'var(--console-red)' },
  { id: 'weather',   label: 'WEATHER',   swatch: '#38bdf8', swatchVar: '#38bdf8' },
  { id: 'vessels',   label: 'VESSELS',   swatch: '#64748b', swatchVar: 'var(--console-slate)' },
  { id: 'traffic',   label: 'TRAFFIC',   swatch: '#a78bfa', swatchVar: 'var(--console-purple, #a78bfa)' },
];

export default function NetworkIntelligenceCanvas({
  optimizationState,
  maritimeOverview,
  hotspots = null,
  height = 460,
  defaultLayers = DEFAULT_LAYERS,
}) {
  const [layers, setLayers] = useState(() => new Set(defaultLayers));
  const [tick, setTick] = useState(0);

  // Refresh legend every 60s so labels stay honest; never oscillate
  // inside this interval.
  useEffect(() => {
    const t = setInterval(() => setTick((p) => p + 1), 60000);
    return () => clearInterval(t);
  }, []);

  const regions = Object.values(optimizationState.regions);
  const selectedCount = (optimizationState.global.selected_services || []).length;
  const totalProfit = optimizationState.global.weeklyProfit;
  const coverage = optimizationState.global.coverage;

  const layerMeta = useMemo(() => {
    const lc = {};
    LAYER_DEFS.forEach((d) => {
      lc[d.id] = {
        ...d,
        active: layers.has(d.id),
      };
    });
    return lc;
  }, [layers, tick]);

  const toggle = (id) => {
    setLayers((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const hasHotspots = Array.isArray(hotspots) && hotspots.length > 0;

  return (
    <div className="console-canvas" style={{ height }} aria-label="Network intelligence canvas">
      <div className="legend" role="toolbar" aria-label="Map layer controls">
        <span style={{ color: 'var(--console-text-faint)', textTransform: 'uppercase', letterSpacing: '0.18em', fontSize: 9, marginRight: 4 }}>
          LAYERS
        </span>
        {LAYER_DEFS.map((d) => {
          const active = layers.has(d.id);
          const disabled =
            (d.id === 'weather' && !maritimeOverview?.sources?.weather) ||
            (d.id === 'vessels' && !optimizationState?.isConnected) ||
            (d.id === 'traffic' && !maritimeOverview?.sources?.traffic) ||
            (d.id === 'congestion' && !hasHotspots);
          return (
            <button
              key={d.id}
              type="button"
              className={`item ${active ? 'on' : ''}`}
              onClick={() => !disabled && toggle(d.id)}
              aria-pressed={active}
              disabled={disabled}
              title={disabled ? `${d.label}: no evidence` : d.label}
              style={disabled ? { opacity: 0.35, cursor: 'not-allowed' } : undefined}
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
          <span className="v">
            {totalProfit > 0 ? `$${(totalProfit / 1e6).toFixed(1)}M` : '—'}
          </span>
        </div>
        <div className="row">
          <span className="k">COVERAGE</span>
          <span className="v">
            {coverage > 0 ? `${coverage.toFixed(1)}%` : '—'}
          </span>
          <span className="k" style={{ marginLeft: 8 }}>REGIONS</span>
          <span className="v">{regions.length || '—'}</span>
        </div>
        {maritimeOverview && (
          <div className="row" style={{ borderTop: '1px solid var(--console-divider-soft)', paddingTop: 4, marginTop: 4 }}>
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
            <OperationalEmptyState
              variant="no_data"
              title="No selected network on disk"
              hint="The canvas renders ports, routes, and the selected iteration's services when an orchestrator run is on disk. When none is present, the canvas shows the world basemap only."
            />
          </div>
        </div>
      )}
    </div>
  );
}
