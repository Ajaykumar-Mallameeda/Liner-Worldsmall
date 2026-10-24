/**
 * MaritimeSituation -- Phase 12 REVISION
 * --------------------------------------
 * The maritime situation instrument. Aggregates weather,
 * congestion, and live maritime layers in one view so the
 * operator can read the operational situation at a glance.
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
function fmtTime(iso) {
  if (!iso) return EM;
  try { return new Date(iso).toISOString().slice(0, 19).replace('T', ' '); }
  catch (_) { return String(iso); }
}
function fmtNum(v) {
  if (v == null) return EM;
  if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (v >= 1e3) return (v / 1e3).toFixed(0) + 'K';
  return String(Math.round(v));
}

function LayerBlock(props) {
  const title = props.title, state = props.state;
  const evaluatedAt = props.evaluatedAt, attribution = props.attribution, license = props.license;
  const children = props.children, empty = props.empty, loading = props.loading, emptyTitle = props.emptyTitle, emptyHint = props.emptyHint;
  const stats = props.stats;
  return h(InstrumentPanel, {
    title: title,
    right: h('span', { style: { display: 'inline-flex', gap: 6, alignItems: 'center' } },
      h(Dot, { tone: state || 'unknown' }),
      h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)', textTransform: 'uppercase', letterSpacing: '0.14em' } }, state || 'unknown')
    ),
  },
    loading
      ? h(Empty, { tone: 'unknown', label: 'loading', title: 'Loading layer' })
      : empty
        ? h(Empty, { tone: 'no_data', label: 'no data', title: emptyTitle || ('No ' + title), hint: emptyHint })
        : h(F, null,
            stats && h('div', { className: 'p12-kv-grid', style: { marginBottom: 10 } }, stats),
            children,
            h('div', { style: { marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--cx-edge-soft)', fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)', letterSpacing: '0.05em', textTransform: 'uppercase' } },
              attribution + ' · ' + license + (evaluatedAt ? (' · eval ' + fmtTime(evaluatedAt)) : '')
            )
          )
  );
}

export default function MaritimeSituation(props) {
  const maritimeOverview = props && props.maritimeOverview;
  const [weather, setWeather] = useState(null);
  const [congestion, setCongestion] = useState(null);
  const [live, setLive] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(function() {
    let cancelled = false;
    const load = async function() {
      if (document.hidden) return;
      try {
        const w = await fetch('/api/maritime/weather/status').then(function(r) { return r.ok ? r.json() : null; });
        const c = await fetch('/api/maritime/congestion/status').then(function(r) { return r.ok ? r.json() : null; });
        const l = await fetch('/api/maritime/live/status').then(function(r) { return r.ok ? r.json() : null; });
        if (cancelled) return;
        if (w) setWeather(w);
        if (c) setCongestion(c);
        if (l) setLive(l);
      } catch (_) { /* noop */ }
      finally { if (!cancelled) setLoading(false); }
    };
    load();
    const t = setInterval(load, 30000);
    return function() { cancelled = true; clearInterval(t); };
  }, []);

  const overallState = maritimeOverview && maritimeOverview.enabled
    ? (maritimeOverview.overall_state || 'available')
    : 'disabled';
  const wState = weather ? (weather.state || weather.freshness_state || 'available') : (loading ? 'unknown' : 'no_data');
  const cState = congestion ? (congestion.state || congestion.freshness_state || 'available') : (loading ? 'unknown' : 'no_data');
  const lState = live ? (live.state || live.freshness_state || 'available') : (loading ? 'unknown' : 'no_data');

  return h(F, null,
    h(PageHead, {
      section: 'Intelligence',
      eyebrow: 'Maritime Situation',
      title: 'Maritime Situation',
      subtitle: 'The operational picture across weather, congestion, and live maritime layers. Each layer is independent and keeps its own provenance. Empty states are typed and honest.',
      pills: [
        { tone: overallState, label: maritimeOverview && maritimeOverview.enabled ? (overallState === 'live' ? 'LIVE' : overallState) : 'disabled' },
        { tone: wState, label: 'weather · ' + wState },
        { tone: cState, label: 'congestion · ' + cState },
        { tone: lState, label: 'live · ' + lState },
      ],
    }),

    h('div', { className: 'cx-page-body' },

      overallState === 'disabled' && h('div', { className: 'cx-compact-empty', role: 'status', style: { border: '1px solid var(--cx-edge)', marginBottom: 12 } },
        'Maritime intelligence is off for this run (MARITIME_INTELLIGENCE_ENABLED=0), so the weather, congestion and live layers below have no snapshots. The optimizer used the dataset files only. Set MARITIME_INTELLIGENCE_ENABLED=1 on the backend to turn the layers on.'),

      h('div', { className: 'cx-grid-12' },
        h('div', { className: 'cx-span-4' },
          h(LayerBlock, {
            title: 'Weather',
            subtitle: 'Open-Meteo (non-commercial) + NOAA NWS (public domain). Read-only FeatureAdapter.',
            state: wState,
            evaluatedAt: weather && weather.evaluated_at,
            attribution: 'Open-Meteo + NOAA NWS',
            license: 'non-commercial / public domain',
            loading: loading && !weather,
            empty: !loading && (!weather || !weather.snapshot_id),
            emptyTitle: 'No weather snapshot',
            emptyHint: 'The weather FeatureAdapter has not produced a snapshot on disk yet.',
            stats: weather ? [
              h(Kv, { k: 'providers', v: fmtNum(weather.provider_count || (weather.providers ? weather.providers.length : 0)) }),
              h(Kv, { k: 'forecasts', v: fmtNum(weather.forecast_count) }),
              h(Kv, { k: 'last sync', v: weather.last_sync ? fmtTime(weather.last_sync) : EM }),
            ] : null,
          },
            weather && weather.forecasts ? h('div', { className: 'cx-rows' },
              (weather.forecasts || []).slice(0, 6).map(function(f, i) {
                return h('div', { key: i, className: 'cx-row', style: { padding: '6px 10px' } },
                  h('div', null,
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text)' } }, f.region || f.area || 'region ' + (i + 1)),
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)' } }, f.timestamp ? fmtTime(f.timestamp) : EM)
                  ),
                  h('div', null,
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text)' } }, f.wind_kt ? (f.wind_kt + ' kt') : (f.wind_speed ? (f.wind_speed + ' kt') : EM)),
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)' } }, 'wave ' + (f.wave_height_m || 0).toFixed(1) + 'm')
                  )
                );
              })
            ) : null
          )
        ),
        h('div', { className: 'cx-span-4' },
          h(LayerBlock, {
            title: 'Congestion',
            subtitle: 'AIS-derived hotspot layer. Active congestion cells and their severity.',
            state: cState,
            evaluatedAt: congestion && congestion.evaluated_at,
            attribution: 'AIS-derived',
            license: 'derived · non-commercial',
            loading: loading && !congestion,
            empty: !loading && (!congestion || !congestion.snapshot_id),
            emptyTitle: 'No congestion snapshot',
            emptyHint: 'The congestion pipeline has not produced a snapshot on disk yet.',
            stats: congestion ? [
              h(Kv, { k: 'hotspots', v: fmtNum(congestion.hotspot_count) }),
              h(Kv, { k: 'cells', v: fmtNum(congestion.cells) }),
              h(Kv, { k: 'last sync', v: congestion.last_sync ? fmtTime(congestion.last_sync) : EM }),
            ] : null,
          },
            congestion && congestion.hotspots ? h('div', { className: 'cx-rows' },
              (congestion.hotspots || []).slice(0, 6).map(function(hs, i) {
                return h('div', { key: i, className: 'cx-row', style: { padding: '6px 10px' } },
                  h('div', null,
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text)' } }, hs.region || hs.area || ('hotspot ' + (i + 1))),
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)' } }, 'severity ' + (hs.severity || EM))
                  ),
                  h('div', null,
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text)' } }, hs.vessels ? (hs.vessels + ' vessels') : EM),
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)' } }, hs.density ? (hs.density + ' / km²') : EM)
                  )
                );
              })
            ) : null
          )
        ),
        h('div', { className: 'cx-span-4' },
          h(LayerBlock, {
            title: 'Live Maritime',
            subtitle: 'AISStream (DEV_ONLY) live positions. Synthetic when no live credentials.',
            state: lState,
            evaluatedAt: live && live.evaluated_at,
            attribution: 'AISStream',
            license: 'DEV_ONLY',
            loading: loading && !live,
            empty: !loading && (!live || !live.snapshot_id),
            emptyTitle: 'No live maritime feed',
            emptyHint: 'AISStream is disabled in this environment; live positions are not observed.',
            stats: live ? [
              h(Kv, { k: 'vessels', v: fmtNum(live.vessel_count) }),
              h(Kv, { k: 'streams', v: fmtNum(live.stream_count) }),
              h(Kv, { k: 'last seen', v: live.last_seen ? fmtTime(live.last_seen) : EM }),
            ] : null,
          },
            live && live.vessels ? h('div', { className: 'cx-rows' },
              (live.vessels || []).slice(0, 6).map(function(v, i) {
                return h('div', { key: i, className: 'cx-row', style: { padding: '6px 10px' } },
                  h('div', null,
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text)' } }, v.mmsi || ('vessel ' + (i + 1))),
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)' } }, v.vessel_type || EM)
                  ),
                  h('div', null,
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text)' } }, v.speed_kt ? (v.speed_kt + ' kt') : EM),
                    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)' } }, v.course ? (v.course + ' deg') : EM)
                  )
                );
              })
            ) : null
          )
        )
      ),

      h(Provenance, {
        source: 'maritime weather / congestion / live pipeline',
        sourceStatus: overallState,
        attribution: 'Open-Meteo, NOAA NWS, AISStream, EMODnet, NOAA MarineCadastre, Fintraffic Digitraffic',
        license: 'Mixed open-data / non-commercial',
        recordCount: (weather && weather.forecast_count) || 0,
        snapshotId: maritimeOverview && maritimeOverview.snapshot_id,
      })
    )
  );
}
