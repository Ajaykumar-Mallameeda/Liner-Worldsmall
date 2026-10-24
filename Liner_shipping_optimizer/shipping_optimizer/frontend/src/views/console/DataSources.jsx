/**
 * DataSources -- Phase 12 REVISION
 * --------------------------------
 * The Data Sources instrument. A complete roll-up of every
 * maritime data source the system knows about, with
 * attribution, license, state, and last evaluation time.
 * Honest empty / disabled states.
 *
 * Data contracts UNCHANGED.
 */

import { useEffect, useState, createElement, Fragment } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Pill, Kv, Stat, Empty, Tag, Dot, Provenance } from '../../components/console/p12.jsx';
const h = createElement;
const F = Fragment;

const EM = '—';
function fmtNum(v) {
  if (v == null) return EM;
  if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (v >= 1e3) return (v / 1e3).toFixed(0) + 'K';
  return String(Math.round(v));
}

const STATIC_PROVIDERS = [
  { id: 'emodnet',              name: 'EMODnet',                   license: 'CC-BY',                              attribution: 'EMODnet (European Marine Observation and Data Network)' },
  { id: 'noaa_marinecadastre',  name: 'NOAA MarineCadastre',       license: 'CC0 (US Government public domain)',  attribution: 'NOAA MarineCadastre' },
  { id: 'noaa_nws',             name: 'NOAA NWS',                  license: 'Public domain',                      attribution: 'NOAA National Weather Service' },
  { id: 'open_meteo',           name: 'Open-Meteo',                license: 'Non-commercial / open-data',         attribution: 'Open-Meteo' },
  { id: 'fintraffic_digitraffic',name: 'Fintraffic Digitraffic',   license: 'CC-BY',                              attribution: 'Fintraffic Digitraffic' },
  { id: 'aisstream',            name: 'AISStream (DEV_ONLY)',      license: 'Non-commercial / DEV_ONLY',          attribution: 'AISStream (development-only)' },
];

export default function DataSources(props) {
  const maritimeOverview = props && props.maritimeOverview;
  const [sources, setSources] = useState([]);
  const [enabled, setEnabled] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(function() {
    let cancelled = false;
    const load = async function() {
      try {
        const r = await fetch('/api/maritime/sources');
        if (r.ok && !cancelled) {
          const j = await r.json();
          if (cancelled) return;
          setEnabled(j.enabled != null ? j.enabled : false);
          setSources(j.sources || []);
        }
      } catch (_) { if (!cancelled) setEnabled(false); }
      finally { if (!cancelled) setLoading(false); }
    };
    load();
    return function() { cancelled = true; };
  }, []);

  const overviewSources = maritimeOverview && maritimeOverview.sources ? maritimeOverview.sources : {};
  const merged = STATIC_PROVIDERS.map(function(p) {
    const s = sources.find(function(x) {
      return String(x.source || '').toLowerCase().includes(p.id) || String(x.source || '').toLowerCase() === p.id;
    });
    const o = overviewSources[p.id] || overviewSources[p.id.toUpperCase()] || null;
    return {
      id: p.id,
      name: p.name,
      license: p.license,
      attribution: p.attribution,
      record_count: (s && s.record_count != null) ? s.record_count : (o && o.record_count),
      snapshot_id: (s && s.snapshot_id) || (o && o.snapshot_id),
      state: (s && (s.source_status || s.quality_status)) || (o && o.state) || 'unknown',
      quality: o && o.quality_score,
      ageSeconds: o && o.freshness_seconds,
    };
  });

  const overallState = enabled ? 'available' : 'disabled';
  const liveCount = merged.filter(function(m) { return m.state === 'available' || m.state === 'live'; }).length;
  const degradedCount = merged.filter(function(m) { return m.state === 'degraded' || m.state === 'stale'; }).length;
  const offlineCount = merged.filter(function(m) { return m.state === 'offline' || m.state === 'error' || m.state === 'down'; }).length;

  return h(F, null,
    h(PageHead, {
      section: 'System',
      eyebrow: 'Data Sources',
      title: 'Data Sources',
      subtitle: 'Every maritime data source the system knows about, with attribution, license, and honest state. The system never claims a source is live when it is not.',
      pills: [
        { tone: overallState, label: enabled ? 'maritime enabled' : 'maritime disabled' },
        { tone: liveCount > 0 ? 'available' : 'unknown', label: liveCount + ' live' },
        { tone: degradedCount > 0 ? 'degraded' : 'muted', label: degradedCount + ' degraded' },
        { tone: offlineCount > 0 ? 'offline' : 'muted', label: offlineCount + ' offline' },
      ],
    }),

    h('div', { className: 'cx-page-body' },

      h('div', { className: 'cx-grid-12' },
        merged.map(function(m) {
          const st = m.state;
          return h('div', { key: m.id, className: 'cx-span-4' },
            h(InstrumentPanel, {
              title: m.name,
              right: h('span', { style: { display: 'inline-flex', gap: 6, alignItems: 'center' } },
                h(Dot, { tone: st }),
                h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)', textTransform: 'uppercase', letterSpacing: '0.14em' } }, st)
              ),
              bodyPadding: 'flush',
            },
              h('div', { className: 'p12-kv-grid', style: { padding: '10px 12px' } },
                h(Kv, { k: 'license', v: m.license || EM }),
                h(Kv, { k: 'records', v: m.record_count != null ? fmtNum(m.record_count) : EM }),
                h(Kv, { k: 'snapshot', v: m.snapshot_id || EM }),
                h(Kv, { k: 'age', v: m.ageSeconds != null ? (m.ageSeconds + 's') : EM }),
                h(Kv, { k: 'quality', v: m.quality != null ? Number(m.quality).toFixed(2) : EM })
              ),
              h('div', { style: { padding: '8px 12px', borderTop: '1px solid var(--cx-edge-soft)', fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)' } }, m.attribution)
            )
          );
        })
      ),

      h(InstrumentPanel, {
        title: 'Aggregate Source Health',
        right: 'the roll-up from the maritime overview',
        bodyPadding: 'flush',
      },
        loading
          ? h(Empty, { tone: 'unknown', label: 'loading', title: 'Loading sources' })
          : Object.keys(overviewSources).length === 0
            ? h(Empty, { tone: 'no_data', label: 'no rollup', title: 'No source health reported' })
            : h('div', { className: 'cx-rows' },
                h('div', { className: 'cx-row', style: { fontWeight: 500, color: 'var(--cx-text-faint)' } },
                  h('div', null, 'SOURCE'),
                  h('div', null, 'DATASET'),
                  h('div', null, 'STATE'),
                  h('div', { style: { textAlign: 'right' } }, 'RECORDS'),
                  h('div', null, 'FRESHNESS'),
                  h('div', { style: { textAlign: 'right' } }, 'QUALITY')
                ),
                Object.entries(overviewSources).map(function(entry) {
                  const key = entry[0], cell = entry[1] || {};
                  return h('div', { key: key, className: 'cx-row' },
                    h('div', { style: { color: 'var(--cx-text)', textTransform: 'uppercase', letterSpacing: '0.1em', fontFamily: 'var(--cx-mono)', fontSize: 12 } }, key),
                    h('div', { style: { color: 'var(--cx-text-dim)' } }, cell.dataset || key),
                    h('div', null,
                      h('span', { style: { display: 'inline-flex', gap: 6, alignItems: 'center' } },
                        h(Dot, { tone: cell.state || 'unknown' }),
                        h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12 } }, cell.state || 'unknown')
                      )
                    ),
                    h('div', { style: { textAlign: 'right', color: 'var(--cx-text-dim)' } }, cell.record_count != null ? fmtNum(cell.record_count) : EM),
                    h('div', { style: { color: 'var(--cx-text-dim)' } }, cell.freshness_seconds != null ? (cell.freshness_seconds + 's') : EM),
                    h('div', { style: { textAlign: 'right', color: 'var(--cx-text-dim)' } }, cell.quality_score != null ? Number(cell.quality_score).toFixed(2) : EM)
                  );
                })
              )
      ),

      h(Provenance, {
        source: '/api/maritime/sources + maritime overview',
        sourceStatus: enabled ? 'available' : 'disabled',
        attribution: 'EMODnet, NOAA MarineCadastre, NOAA NWS, Open-Meteo, Fintraffic Digitraffic, AISStream (DEV_ONLY)',
        license: 'Mixed open-data / non-commercial',
      })
    )
  );
}
