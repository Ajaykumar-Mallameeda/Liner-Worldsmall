/**
 * FleetIntelligence -- Phase 12 REVISION
 * --------------------------------------
 * The fleet instrument. Vessel class mix from the selected
 * iteration, per-region fleet breakdown, AIS / live observation
 * honesty. Real evidence only.
 *
 * Data contracts UNCHANGED.
 */

import { useEffect, useMemo, useState, createElement, Fragment } from 'react';
import { useOptimizationState } from '../../hooks/useOptimizationState.js';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Pill, Kv, Stat, Empty, Provenance } from '../../components/console/p12.jsx';
const h = createElement;
const F = Fragment;

const EM = '—';
function fmtNum(v) {
  if (v == null || v !== v) return EM;
  const n = Number(v);
  const neg = n < 0;
  const abs = Math.abs(n);
  let s = abs >= 1e9 ? (abs / 1e9).toFixed(2) + 'B'
        : abs >= 1e6 ? (abs / 1e6).toFixed(1) + 'M'
        : abs >= 1e3 ? (abs / 1e3).toFixed(0) + 'K'
        : String(Math.round(abs));
  return neg ? '-' + s : s;
}

function fmtUsd(v) {
  if (v == null || v !== v) return EM;
  const n = Number(v);
  const neg = n < 0;
  const abs = Math.abs(n);
  let s = abs >= 1e9 ? '$' + (abs / 1e9).toFixed(2) + 'B'
        : abs >= 1e6 ? '$' + (abs / 1e6).toFixed(1) + 'M'
        : abs >= 1e3 ? '$' + (abs / 1e3).toFixed(0) + 'K'
        : '$' + Math.round(abs);
  return neg ? '-' + s : s;
}

function regionColor(r) {
  return {
    asia: '#00d4ff',
    europe: '#7c3aed',
    americas: '#10b981',
    middle_east: '#f59e0b',
    africa: '#ef4444',
  }[String(r || '').toLowerCase()] || '#94a3b8';
}

export default function FleetIntelligence(props) {
  const optStateProp = props && props.optimizationState;
  const runtimeProp = props && props.runtime;
  const maritimeOverview = props && props.maritimeOverview;
  const hookState = useOptimizationState();
  const optState = optStateProp || hookState;
  const sm = (runtimeProp && runtimeProp.global) || optState.global || {};
  const regions = (runtimeProp && runtimeProp.regions) || optState.regions || {};
  const [telemetry, setTelemetry] = useState(null);

  useEffect(function() {
    let cancelled = false;
    const load = async function() {
      try {
        const r = await fetch('/api/maritime/telemetry');
        if (r.ok && !cancelled) setTelemetry(await r.json());
      } catch (_) { /* noop */ }
    };
    load();
    return function() { cancelled = true; };
  }, []);

  const selectedServices = (runtimeProp && runtimeProp.selected_services) ||
    sm.selected_services ||
    (optState && optState.selectedServices) ||
    [];
  const totalSelected = selectedServices.length || sm.totalServices || 0;
  const fleetState = (maritimeOverview && maritimeOverview.fleet) || (telemetry && telemetry.fleet) || null;

  // Derive vessel-class mix
  const vesselClassStats = useMemo(function() {
    const map = {};
    for (let i = 0; i < selectedServices.length; i++) {
      const s = selectedServices[i];
      const cls = s.vessel_class || 'Standard';
      if (!map[cls]) {
        map[cls] = { count: 0, capacity: 0, load: 0, profit: 0, carriedLegs: 0, offeredLegs: 0, hasLegs: false };
      }
      map[cls].count += 1;
      map[cls].capacity += Number(s.capacity || 0);
      map[cls].load += Number(s.load || 0);
      map[cls].profit += Number(s.weekly_profit || 0);
      if (s.offered_teu_legs != null && s.carried_teu_legs != null) {
        map[cls].carriedLegs += Number(s.carried_teu_legs);
        map[cls].offeredLegs += Number(s.offered_teu_legs);
        map[cls].hasLegs = true;
      }
    }
    return map;
  }, [selectedServices]);

  const totalCapacity = Object.values(vesselClassStats).reduce(function(acc, s) { return acc + (s.capacity || 0); }, 0);
  const totalLoad = Object.values(vesselClassStats).reduce(function(acc, s) { return acc + (s.load || 0); }, 0);
  // leg load factor from the ledger's carried / offered TEU-legs; weekly cargo / per-departure capacity is not a utilisation
  const carriedLegsAll = Object.values(vesselClassStats).reduce(function(acc, s) { return acc + (s.carriedLegs || 0); }, 0);
  const offeredLegsAll = Object.values(vesselClassStats).reduce(function(acc, s) { return acc + (s.offeredLegs || 0); }, 0);
  const utilization = offeredLegsAll > 0 ? (carriedLegsAll / offeredLegsAll) * 100 : null;
  const overallState = totalSelected > 0 ? 'available' : 'no_data';

  return h(F, null,
    h(PageHead, {
      section: 'Intelligence',
      eyebrow: 'Fleet',
      title: 'Fleet Intelligence',
      subtitle: 'A view of the fleet in the selected iteration. The dashboard reads vessel assignments from the deterministic selection; AIS / live vessel positions are explicitly labeled when absent.',
      pills: [
        { tone: overallState, label: totalSelected > 0 ? 'on disk' : 'no data' },
        { tone: fleetState && fleetState.vessels_observed != null ? 'live' : 'not_observed', label: fleetState && fleetState.vessels_observed != null ? 'AIS observed' : 'AIS not observed' },
      ],
    }),

    h('div', { className: 'cx-page-body' },

      // ── TOP ROW: 4 Telemetry Cards (Aligned Heights) ──
      h('div', { className: 'cx-grid-12 sa-row-stretch', style: { marginBottom: 12 } },
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Selected Services', right: 'fleet · synth', style: { height: '100%', display: 'flex', flexDirection: 'column' } },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } },
              h(Stat, { k: 'selected', v: fmtNum(totalSelected), variant: 'accent', sub: 'across ' + Object.keys(regions).length + ' regions' }),
              h('div', {
                style: {
                  display: 'flex', justifyContent: 'space-between',
                  fontFamily: 'var(--cx-mono)', fontSize: 8,
                  color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                  paddingTop: 4, marginTop: 4,
                },
              },
                h('span', null, 'Fleet Services'),
                h('span', { style: { color: 'var(--cx-cyan-2)' } }, `${totalSelected} Active`),
              ),
            )
          )
        ),
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Vessels (Synthesized)', right: '1:1 with services', style: { height: '100%', display: 'flex', flexDirection: 'column' } },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } },
              h(Stat, { k: 'vessels', v: fmtNum(totalSelected), sub: '1 vessel per selected service' }),
              h('div', {
                style: {
                  display: 'flex', justifyContent: 'space-between',
                  fontFamily: 'var(--cx-mono)', fontSize: 8,
                  color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                  paddingTop: 4, marginTop: 4,
                },
              },
                h('span', null, 'Assignment'),
                h('span', { style: { color: 'var(--cx-text-dim)' } }, '1:1 Model'),
              ),
            )
          )
        ),
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Vessels Observed (AIS)', right: fleetState ? 'live' : 'not observed', style: { height: '100%', display: 'flex', flexDirection: 'column' } },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } },
              h(Stat, {
                k: 'observed',
                v: (fleetState && fleetState.vessels_observed != null) ? fmtNum(fleetState.vessels_observed) : EM,
                variant: (fleetState && fleetState.vessels_observed != null) ? 'good' : 'muted',
                sub: (fleetState && fleetState.vessels_observed != null) ? 'EMODnet density + live' : 'no AIS on disk'
              }),
              h('div', {
                style: {
                  display: 'flex', justifyContent: 'space-between',
                  fontFamily: 'var(--cx-mono)', fontSize: 8,
                  color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                  paddingTop: 4, marginTop: 4,
                },
              },
                h('span', null, 'AIS Stream'),
                h('span', { style: { color: (fleetState && fleetState.vessels_observed != null) ? 'var(--cx-green)' : 'var(--cx-text-faint)' } }, (fleetState && fleetState.vessels_observed != null) ? 'Live Stream' : 'Not Observed'),
              ),
            )
          )
        ),
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, { title: 'Leg Load Factor', right: 'carried / offered TEU-legs', style: { height: '100%', display: 'flex', flexDirection: 'column' } },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } },
              h(Stat, {
                k: 'util',
                v: utilization != null ? (utilization.toFixed(1) + '%') : EM,
                variant: utilization != null ? 'good' : 'muted',
                sub: fmtNum(carriedLegsAll) + ' / ' + fmtNum(offeredLegsAll) + ' TEU-legs'
              }),
              h('div', {
                style: {
                  display: 'flex', justifyContent: 'space-between',
                  fontFamily: 'var(--cx-mono)', fontSize: 8,
                  color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                  paddingTop: 4, marginTop: 4,
                },
              },
                h('span', null, 'Total Capacity'),
                h('span', { style: { color: 'var(--cx-cyan-2)' } }, `${fmtNum(totalCapacity)} TEU`),
              ),
            )
          )
        )
      ),

      // ── MIDDLE ROW: Vessel Class Mix & Regional Fleet (Aligned Heights) ──
      h('div', { className: 'cx-grid-12 sa-row-stretch', style: { marginBottom: 12 } },
        h('div', { className: 'cx-span-6' },
          h(InstrumentPanel, {
            title: 'Vessel Class Mix',
            right: 'real evidence: selected_services[].vessel_class',
            bodyPadding: 'flush',
            style: { height: '100%', display: 'flex', flexDirection: 'column' },
          },
            Object.keys(vesselClassStats).length === 0
              ? h(Empty, { tone: 'no_data', label: 'no classes', title: 'No selected services', hint: 'Re-run the orchestrator to populate the vessel class mix.' })
              : h('div', { className: 'cx-rows flex-1 flex flex-col justify-between' },
                  h('div', { className: 'flex-1 flex flex-col justify-between' },
                    Object.entries(vesselClassStats).map(function(entry) {
                      const c = entry[0], st = entry[1];
                      const pct = totalSelected > 0 ? (st.count / totalSelected) * 100 : 0;
                      return h('div', { key: c, className: 'cx-row', style: { display: 'block', padding: '8px 10px', flex: 1 } },
                        h('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 } },
                          h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 11, color: 'var(--cx-text)', textTransform: 'uppercase', letterSpacing: '0.1em' } }, c),
                          h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 9, color: 'var(--cx-text-faint)' } }, st.count + ' services · ' + fmtUsd(st.profit))
                        ),
                        h('div', { style: { display: 'flex', gap: 12, alignItems: 'center' } },
                          h('div', { style: { flex: 1, height: 4, background: 'var(--cx-edge)', position: 'relative' } },
                            h('div', { style: { position: 'absolute', left: 0, top: 0, bottom: 0, width: pct + '%', background: 'var(--cx-cyan)' } })
                          ),
                          h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 10, color: 'var(--cx-text-dim)', minWidth: 36, textAlign: 'right' } }, pct.toFixed(0) + '%')
                        ),
                        h('div', { className: 'p12-kv-grid', style: { marginTop: 6 } },
                          h(Kv, { k: 'capacity', v: fmtNum(st.capacity) }),
                          h(Kv, { k: 'load', v: fmtNum(st.load) }),
                          h(Kv, { k: 'util', v: st.capacity > 0 ? ((st.load / st.capacity) * 100).toFixed(1) + '%' : EM })
                        )
                      );
                    })
                  ),
                  h('div', {
                    style: {
                      display: 'flex', justifyContent: 'space-between',
                      fontFamily: 'var(--cx-mono)', fontSize: 8,
                      color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                      padding: '6px 10px', background: 'rgba(0,0,0,0.1)',
                    },
                  },
                    h('span', null, `Total: ${Object.keys(vesselClassStats).length} Vessel Classes`),
                    h('span', { style: { color: 'var(--cx-cyan-2)' } }, `${fmtNum(totalCapacity)} TEU Capacity`),
                  )
                )
          )
        ),
        h('div', { className: 'cx-span-6' },
          h(InstrumentPanel, {
            title: 'Regional Fleet',
            right: 'real evidence: regional_results[].services_selected + weekly_profit',
            bodyPadding: 'flush',
            style: { height: '100%', display: 'flex', flexDirection: 'column' },
          },
            Object.keys(regions).length === 0
              ? h(Empty, { tone: 'no_data', label: 'no regions', title: 'No regional data', hint: 'Re-run the orchestrator to populate the regional fleet.' })
              : h('div', { className: 'cx-rows flex-1 flex flex-col justify-between' },
                  h('div', { className: 'flex-1 flex flex-col justify-between' },
                    Object.entries(regions).map(function(entry) {
                      const id = entry[0], r = entry[1];
                      return h('div', { key: id, className: 'cx-row', style: { display: 'block', padding: '8px 10px', flex: 1 } },
                        h('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 } },
                          h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 11, letterSpacing: '0.14em', color: regionColor(id), textTransform: 'uppercase' } }, r.name || id),
                          h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 9, color: 'var(--cx-text-faint)' } }, 'region')
                        ),
                        h('div', { className: 'p12-kv-grid' },
                          h(Kv, { k: 'services', v: fmtNum(r.services) }),
                          h(Kv, { k: 'P&L', v: fmtUsd(r.profit) }),
                          h(Kv, { k: 'coverage', v: r.coverage != null ? (Number(r.coverage).toFixed(1) + '%') : EM }),
                          h(Kv, { k: 'ports', v: fmtNum(r.ports) })
                        )
                      );
                    })
                  ),
                  h('div', {
                    style: {
                      display: 'flex', justifyContent: 'space-between',
                      fontFamily: 'var(--cx-mono)', fontSize: 8,
                      color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                      padding: '6px 10px', background: 'rgba(0,0,0,0.1)',
                    },
                  },
                    h('span', null, `Total: ${Object.keys(regions).length} Regional Fleets`),
                    h('span', { style: { color: 'var(--cx-cyan-2)' } }, `${fmtNum(totalSelected)} Vessels Deployed`),
                  )
                )
          )
        )
      ),

      // ── BOTTOM SECTION: AIS / Live Observations ──
      h(InstrumentPanel, {
        title: 'AIS / Live Vessel Observations',
        right: 'maritime telemetry — absent state is honest, not fabricated',
        bodyPadding: 'flush',
      },
        fleetState && fleetState.vessels_observed != null
          ? h('div', { className: 'cx-grid-12' },
              h('div', { className: 'cx-span-4' },
                h(Stat, { k: 'EMODnet density', v: fmtNum(fleetState._meta && fleetState._meta.emodnet_vessels), sub: 'AIS-like density layer' })
              ),
              h('div', { className: 'cx-span-4' },
                h(Stat, { k: 'Live vessels', v: fmtNum(fleetState._meta && fleetState._meta.live_vessels), sub: 'AISStream (DEV_ONLY)' })
              ),
              h('div', { className: 'cx-span-4' },
                h(Stat, { k: 'Weather risk', v: fleetState.weather_risk != null ? Number(fleetState.weather_risk).toFixed(2) : EM, sub: 'aggregate' })
              )
            )
          : h(Empty, {
              tone: 'not_observed',
              label: 'not observed',
              title: 'No AIS / live vessel data observed',
              hint: 'Live vessel telemetry is not enabled in this environment. Set MARITIME_INTELLIGENCE_ENABLED=1 to ingest real-time feeds.',
            })
      ),

      // ── PROVENANCE FOOTER ──
      h(Provenance, {
        source: 'pipeline_output.json (selected_services[].vessel_class, regional_results)',
        sourceStatus: totalSelected > 0 ? 'available' : 'no_data',
        attribution: 'EMODnet, NOAA MarineCadastre, Open-Meteo, Fintraffic Digitraffic',
        license: 'Mixed open-data / non-commercial',
        recordCount: totalSelected,
      })
    )
  );
}
