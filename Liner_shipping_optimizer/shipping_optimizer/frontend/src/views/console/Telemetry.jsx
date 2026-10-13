/**
 * Telemetry -- Phase 12 REVISION
 * ------------------------------
 * The system Telemetry instrument. Reads real telemetry from
 * /api/maritime/telemetry when available. No setInterval
 * randomizeMetric. No fake live charts. The data is what
 * the backend reports.
 *
 * Data contracts UNCHANGED.
 */

import { useEffect, useState, createElement, Fragment } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Pill, Kv, Stat, Empty, Tag, Sparkline, Provenance } from '../../components/console/p12.jsx';
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

export default function Telemetry(props) {
  const maritimeOverview = props && props.maritimeOverview;
  const [telemetry, setTelemetry] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(function() {
    let cancelled = false;
    const load = async function() {
      try {
        const r = await fetch('/api/maritime/telemetry');
        if (r.ok && !cancelled) setTelemetry(await r.json());
      } catch (_) { /* noop */ }
      finally { if (!cancelled) setLoading(false); }
    };
    load();
    const t = setInterval(load, 30000);
    return function() { cancelled = true; clearInterval(t); };
  }, []);

  const fleet = telemetry && telemetry.fleet ? telemetry.fleet : null;
  const sources = telemetry && telemetry.sources ? telemetry.sources : null;
  const freshness = telemetry && telemetry.freshness ? telemetry.freshness : null;
  const wsState = telemetry && telemetry.ws ? telemetry.ws : null;
  const overallState = !telemetry
    ? 'no_data'
    : (fleet && fleet.vessels_observed != null ? 'partial' : 'offline');

  return h(F, null,
    h(PageHead, {
      section: 'System',
      eyebrow: 'Telemetry',
      title: 'System Telemetry',
      subtitle: 'Real telemetry from the maritime data plane. The dashboard reads /api/maritime/telemetry on a 30s cadence; nothing here is randomized or fabricated.',
      pills: [
        { tone: overallState, label: overallState },
        { tone: wsState ? 'connected' : 'offline', label: wsState ? 'ws link' : 'ws off' },
        { tone: telemetry ? 'available' : 'no_data', label: telemetry ? 'telemetry' : 'no telemetry' },
      ],
    }),

    h('div', { className: 'cx-page-body' },

      loading
        ? h(Empty, { tone: 'unknown', label: 'loading', title: 'Loading telemetry' })
        : !telemetry
          ? h(Empty, { tone: 'no_data', label: 'no telemetry', title: 'No telemetry endpoint response', hint: 'The backend did not respond to /api/maritime/telemetry. The dashboard will not fabricate telemetry.' })
          : h(F, null,
              h('div', { className: 'cx-grid-12' },
                h('div', { className: 'cx-span-3' },
                  h(InstrumentPanel, { title: 'Vessels Observed', right: 'EMODnet + live' },
                    h(Stat, { k: 'observed', v: fmtNum(fleet && fleet.vessels_observed), variant: 'accent', sub: fleet && fleet._meta && fleet._meta.live_vessels != null ? (fmtNum(fleet._meta.live_vessels) + ' live') : 'snapshot' })
                  )
                ),
                h('div', { className: 'cx-span-3' },
                  h(InstrumentPanel, { title: 'Ports Observed', right: 'local snapshot' },
                    h(Stat, { k: 'ports', v: fmtNum(fleet && fleet.ports_observed), sub: 'from snapshot' })
                  )
                ),
                h('div', { className: 'cx-span-3' },
                  h(InstrumentPanel, { title: 'Weather Risk', right: 'aggregated' },
                    h(Stat, { k: 'risk', v: fleet && fleet.weather_risk != null ? Number(fleet.weather_risk).toFixed(2) : EM, sub: 'aggregate' })
                  )
                ),
                h('div', { className: 'cx-span-3' },
                  h(InstrumentPanel, { title: 'WebSocket', right: 'pipeline' },
                    h(Stat, { k: 'ws', v: (wsState && wsState.state) || EM, sub: wsState && wsState.last_event_at ? ('last ' + fmtTime(wsState.last_event_at)) : 'no events' })
                  )
                )
              ),

              sources && Object.keys(sources).length > 0
                ? h(InstrumentPanel, {
                    title: 'Per-Source Telemetry',
                    right: 'per-source record counts and freshness',
                    bodyPadding: 'flush',
                  },
                  h('div', { className: 'cx-rows' },
                    h('div', { className: 'cx-row', style: { fontWeight: 500, color: 'var(--cx-text-faint)' } },
                      h('div', null, 'SOURCE'),
                      h('div', null, 'STATE'),
                      h('div', { style: { textAlign: 'right' } }, 'RECORDS'),
                      h('div', null, 'FRESHNESS'),
                      h('div', null, 'LICENSE')
                    ),
                    Object.entries(sources).map(function(entry) {
                      const key = entry[0], cell = entry[1];
                      return h('div', { key: key, className: 'cx-row' },
                        h('div', { style: { color: 'var(--cx-text)', textTransform: 'uppercase', letterSpacing: '0.1em', fontFamily: 'var(--cx-mono)', fontSize: 11 } }, key),
                        h('div', { style: { color: 'var(--cx-text)' } }, cell.state || EM),
                        h('div', { style: { textAlign: 'right', color: 'var(--cx-text-dim)' } }, fmtNum(cell.record_count) + ' rec'),
                        h('div', { style: { color: 'var(--cx-text-dim)' } }, cell.freshness_seconds != null ? (cell.freshness_seconds + 's old') : EM),
                        h('div', { style: { color: 'var(--cx-text-faint)' } }, cell.license || EM)
                      );
                    })
                  )
                )
                : null,

              freshness && Object.keys(freshness).length > 0
                ? h(InstrumentPanel, {
                    title: 'Freshness',
                    right: 'per-source freshness in seconds since last snapshot',
                    bodyPadding: 'flush',
                  },
                  h('div', { className: 'cx-rows' },
                    Object.entries(freshness).map(function(entry) {
                      const key = entry[0], age = entry[1];
                      return h('div', { key: key, className: 'cx-row', style: { padding: '8px 10px' } },
                        h('div', { style: { color: 'var(--cx-text)', textTransform: 'uppercase', letterSpacing: '0.1em', fontFamily: 'var(--cx-mono)', fontSize: 11 } }, key),
                        h('div', null,
                          h('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
                            h('div', { style: { flex: 1, height: 4, background: 'var(--cx-edge)', position: 'relative' } },
                              h('div', { style: { position: 'absolute', left: 0, top: 0, bottom: 0, width: Math.min(100, age) + '%', background: 'var(--cx-warn)' } })
                            ),
                            h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 10, color: 'var(--cx-text-dim)' } }, fmtNum(age) + 's')
                          )
                        )
                      );
                    })
                  )
                )
                : null
            ),

      h(Provenance, {
        source: '/api/maritime/telemetry',
        sourceStatus: telemetry ? 'available' : 'no_data',
        attribution: 'Maritime data plane',
        license: 'Internal',
      })
    )
  );
}
