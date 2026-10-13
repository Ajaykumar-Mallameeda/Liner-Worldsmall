/**
 * SourceLayerRail
 * ---------------
 * Phase 10 — a persistent source-filter rail that any maritime
 * view can mount above its content. Default = "all" preserves
 * the Phase 8/9 baseline.
 *
 * The rail is purely presentational: it filters which sources
 * the parent view shows, but it does not change the underlying
 * data, does not issue a new HTTP request, and does not hide
 * disabled / offline / stale states — those are still rendered
 * honestly by the per-source indicators.
 *
 * Reuses the existing `MaritimeLayerToggle` primitive so the
 * visual treatment is identical across views.
 */
import { useCallback } from 'react';
import MaritimeLayerToggle from './primitives/MaritimeLayerToggle.jsx';

const SOURCES = [
  { key: 'all', label: 'All sources', source: null },
  { key: 'traffic', label: 'EMODnet', source: 'EMODnet' },
  { key: 'port', label: 'NOAA', source: 'NOAA MarineCadastre' },
  { key: 'weather', label: 'Weather', source: 'Weather' },
  { key: 'congestion', label: 'Congestion', source: 'Congestion' },
  { key: 'live', label: 'Live', source: 'Live' },
];

export default function SourceLayerRail({
  value = 'all',
  onChange,
  scrollable = false,
}) {
  const handle = useCallback(
    (k) => () => {
      if (onChange) onChange(k);
    },
    [onChange],
  );
  const visible = SOURCES.find((s) => s.key === value) || SOURCES[0];
  return (
    <div className={`mc-layer-rail${scrollable ? ' scrollable' : ''}`}>
      <span className="label">layers</span>
      {SOURCES.map((s) => (
        <MaritimeLayerToggle
          key={s.key}
          active={value === s.key}
          onClick={handle(s.key)}
          label={s.label}
        />
      ))}
      <span
        className="ml-auto mono-data"
        style={{
          fontSize: 9,
          color: 'var(--maritime-ink-faint)',
          textTransform: 'uppercase',
          letterSpacing: '0.18em',
        }}
      >
        {visible.key === 'all'
          ? 'rendering all sources'
          : `rendering ${visible.label} only`}
      </span>
    </div>
  );
}
