/**
 * RegionRail
 * ----------
 * A vertical (or horizontal) region-selector rail for the
 * Network Intelligence map. Six mutually-exclusive buttons:
 *
 *   WORLD · AMERICAS · EUROPE · MIDDLE EAST · ASIA PACIFIC · AFRICA
 *
 * When the user picks a region, the parent filters the
 * services/routes/ports that the WorldMap renders.
 *
 * Each region carries the canonical color from runtimeAdapter
 * (the same palette used in the basemap), and a per-region
 * count of services that fall inside it. The count is derived
 * from the live dataset — never hard-coded.
 *
 * "World" is the default and shows the full dataset.
 */

import { useMemo } from 'react';
import { getRegionColor } from '../../runtime/runtimeAdapter.js';

const REGIONS = [
  { id: 'world',       label: 'WORLD',         short: 'WORLD' },
  { id: 'americas',    label: 'AMERICAS',      short: 'AMERICAS' },
  { id: 'europe',      label: 'EUROPE',        short: 'EUROPE' },
  { id: 'middle_east', label: 'MIDDLE EAST',   short: 'MIDDLE EAST' },
  { id: 'asia',        label: 'ASIA PACIFIC',  short: 'ASIA PACIFIC' },
  { id: 'africa',      label: 'AFRICA',        short: 'AFRICA' },
];

function countByRegion(optimizationState) {
  const counts = {
    americas: 0,
    europe: 0,
    middle_east: 0,
    asia: 0,
    africa: 0,
  };
  const services = (optimizationState && optimizationState.global && optimizationState.global.selected_services) || [];
  services.forEach((svc) => {
    const r = String(svc.region || '').toLowerCase();
    if (counts[r] != null) counts[r] += 1;
    // Inter-regional services touch two regions; count them in both.
    if (svc.portRegions && Array.isArray(svc.portRegions)) {
      svc.portRegions.forEach((pr) => {
        const prn = String(pr || '').toLowerCase();
        if (counts[prn] != null) counts[prn] += 1;
      });
    }
  });
  return counts;
}

export default function RegionRail({ value = 'world', onChange, optimizationState, orientation = 'vertical' }) {
  const counts = useMemo(() => countByRegion(optimizationState || {}), [optimizationState]);
  const cls = orientation === 'horizontal' ? 'region-rail region-rail--horizontal' : 'region-rail';

  return (
    <div className={cls} role="toolbar" aria-label="Region filter">
      {REGIONS.map((r) => {
        const active = value === r.id;
        const isWorld = r.id === 'world';
        const swatch = isWorld ? 'var(--cx-cyan-2)' : getRegionColor(r.id);
        const n = isWorld ? null : (counts[r.id] || 0);
        const disabled = !isWorld && n === 0;
        return (
          <button
            key={r.id}
            type="button"
            className={`region-rail-item ${active ? 'is-active' : ''}`}
            onClick={() => !disabled && onChange && onChange(r.id)}
            aria-pressed={active}
            aria-disabled={disabled}
            title={
              disabled
                ? `${r.label}: no services on disk`
                : isWorld
                  ? 'Show full global dataset'
                  : `Filter to ${r.label} (${n} services)`
            }
          >
            <span className="swatch" style={{ background: swatch, boxShadow: active ? `0 0 6px ${swatch}` : 'none' }} />
            <span className="label">{r.short}</span>
            {!isWorld && (
              <span className={`count ${n === 0 ? 'zero' : ''}`}>{n}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

RegionRail.REGIONS = REGIONS;
