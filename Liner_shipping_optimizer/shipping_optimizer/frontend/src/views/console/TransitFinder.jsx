/**
 * TransitFinder.jsx — point-to-point transit finder (2026-10-28, feature #22).
 *
 * Pick an origin and a destination port: every itinerary the plan on screen offers between them, fastest first,
 * from the engine's own path enumeration (POST /api/transit, backend/transit.py → src/network/paths.build_paths):
 * services ridden, transfer ports, transit days (sailing + intermediate port stays + transfer dwell), departures per
 * week, the worst wait for a connecting departure, port charges per TEU, and — when the pair has recorded demand —
 * its transit-time limit and the TEU the flow LP routes on each itinerary. The selected itinerary is drawn on the map.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Provenance } from '../../components/console/p12.jsx';
import WorldMap from '../../components/map/WorldMap.jsx';
import { getSelectedRun, subscribeRun, runLabel } from '../../services/runSelection.js';
import { fmtNum, fmtUsd } from '../../utils/formatters.js';
import { getPortName } from '../../utils/portLookup.js';

const TRANSFER_CHOICES = [[0, 'Direct only'], [1, 'Up to 1 transfer'], [2, 'Up to 2 transfers']];
const ROWS_SHOWN = 15;
const days = (d) => `${d.toFixed(1)} d`;

export default function TransitFinder({ optimizationState = null }) {
  const [run, setRun] = useState(getSelectedRun());
  useEffect(() => subscribeRun(setRun), []);
  const planServices = optimizationState?.global?.selected_services || [];
  const ports = useMemo(() => {
    const calls = new Map();
    planServices.forEach((sv) => [...new Set(sv.ports || [])].forEach((p) => calls.set(p, (calls.get(p) || 0) + 1)));
    return [...calls.keys()].sort().map((code) => ({ code, name: getPortName(code), calls: calls.get(code) }));
  }, [planServices]);

  const [origin, setOrigin] = useState('');
  const [dest, setDest] = useState('');
  const [maxTr, setMaxTr] = useState(2);
  const [pick, setPick] = useState(0);
  const [state, setState] = useState({ status: 'idle', data: null, error: null });
  const reqId = useRef(0);

  // Start on the busiest pair of the plan's two most-called ports, so the page shows an answer straight away.
  useEffect(() => {
    if (origin || ports.length < 2) return;
    const top = [...ports].sort((a, b) => b.calls - a.calls);
    setOrigin(top[0].code); setDest(top[1].code);
  }, [ports, origin]);

  useEffect(() => {
    if (!origin || !dest || origin === dest) { setState({ status: 'idle', data: null, error: null }); return; }
    const id = ++reqId.current;
    setState((s) => ({ ...s, status: 'loading' }));
    setPick(0);
    (async () => {
      try {
        const r = await fetch('/api/transit', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run, origin, destination: dest, max_transfers: maxTr }),
        });
        const body = await r.json().catch(() => null);
        if (id !== reqId.current) return;
        if (!r.ok || !body?.itineraries) {
          const unreachable = !body || (r.status === 500 && !body?.detail);
          setState({ status: unreachable ? 'unavailable' : 'error', data: null, error: body?.detail || `HTTP ${r.status}` });
          return;
        }
        setState({ status: 'ok', data: body, error: null });
      } catch (e) {
        if (id === reqId.current) setState({ status: 'unavailable', data: null, error: String(e?.message || e) });
      }
    })();
  }, [run, origin, dest, maxTr]);

  const data = state.data;
  const rows = data?.itineraries || [];
  const sel = rows[pick] || null;
  const itinerary = useMemo(() => (sel ? { origin: data.origin, destination: data.destination, hubs: sel.hubs, segments: sel.segments } : null), [sel, data]);
  const mapServices = useMemo(() => {
    if (!sel) return [];
    const ids = new Set(sel.segments.map((s) => String(s.service)));
    return planServices.filter((s) => ids.has(String(s.id)));
  }, [sel, planServices]);
  const fastest = rows[0]?.transit_days || 1;
  const slowest = Math.max(fastest, ...rows.slice(0, ROWS_SHOWN).map((r) => r.transit_days));
  const dm = data?.demand;
  const swap = () => { setOrigin(dest); setDest(origin); };

  return (
    <div className="cx-page-body space-y-3">
      <PageHead
        section="Network"
        eyebrow="Transit finder"
        title="Transit finder: port to port on this plan"
        subtitle="Every way the plan on screen can carry a box from one port to another, fastest first: the services ridden, where it transfers, how long it takes and how often it sails. Itineraries come from the engine's own path rules, not a separate router."
        pills={[
          { tone: 'selected', label: runLabel(run, data?.dataset) },
          { tone: state.status === 'ok' ? 'available' : state.status === 'loading' ? 'active' : 'no_data',
            label: state.status === 'ok' ? `${fmtNum(data.itineraries_found)} itinerar${data.itineraries_found === 1 ? 'y' : 'ies'}` : state.status === 'loading' ? 'searching…' : state.status === 'unavailable' ? 'needs backend' : state.status },
        ]}
      />

      <InstrumentPanel title="Route" right={<span className="text-[12px] text-slate-400">ports the plan calls</span>}>
        <div className="tf-controls">
          <PortSelect id="tf-origin" label="From" value={origin} onChange={setOrigin} ports={ports} />
          <button type="button" className="cmp-btn tf-swap" onClick={swap} disabled={!origin || !dest} aria-label="Swap origin and destination" title="Swap origin and destination">⇄</button>
          <PortSelect id="tf-dest" label="To" value={dest} onChange={setDest} ports={ports} />
          <div className="rl-tabs" role="radiogroup" aria-label="Transfers allowed">
            {TRANSFER_CHOICES.map(([k, label]) => (
              <button key={k} type="button" role="radio" aria-checked={maxTr === k} aria-pressed={maxTr === k} className="cmp-btn" onClick={() => setMaxTr(k)}>{label}</button>
            ))}
          </div>
        </div>
        {ports.length === 0 && <p className="text-[12px] text-slate-400 mt-2">No plan loaded: run the optimizer or pick a run in the header.</p>}
        {origin && dest && origin === dest && <p className="dz-warn mt-2">Pick two different ports.</p>}
        {dm && (
          <p className="tf-demand">
            Recorded demand {data.origin} → {data.destination}: <b>{fmtNum(Math.round(dm.weekly_teu))} TEU/wk</b> at {fmtUsd(dm.revenue_per_teu)}/TEU
            {dm.max_transit_days != null ? <>, transit limit <b>{dm.max_transit_days} days</b></> : ', no transit limit in the source'}.
            {' '}The plan's flow LP routes <b>{fmtNum(Math.round(dm.routed_teu))} TEU/wk</b> of it ({fmtNum(Math.round((dm.routed_teu / dm.weekly_teu) * 100))}%).
          </p>
        )}
        {data && !dm && <p className="tf-demand">No recorded demand from {data.origin} to {data.destination}: the itineraries are what the network offers, not what it carries.</p>}
      </InstrumentPanel>

      {state.status === 'error' && <p className="dz-warn">Search failed: {state.error}</p>}
      {state.status === 'unavailable' && <p className="dz-warn">The transit finder needs the backend (POST /api/transit). {state.error}</p>}

      {state.status === 'ok' && rows.length === 0 && (
        <InstrumentPanel title="No itinerary">
          <p className="text-[13px] text-slate-300 max-w-[80ch]">
            No service of this plan reaches {data.destination} from {data.origin} with {maxTr === 0 ? 'no transfer' : `at most ${maxTr} transfer${maxTr === 1 ? '' : 's'}`}.
            {maxTr < 2 ? ' Allow more transfers, or pick another pair.' : ' Pick another pair.'}
          </p>
        </InstrumentPanel>
      )}

      {rows.length > 0 && (
        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-12 xl:col-span-7 min-w-0">
            <InstrumentPanel title="Itineraries, fastest first" right={<span className="text-[12px] text-slate-400">pick a row to map it</span>} bodyPadding="flush">
              <div className="tf-scroll">
                <table className="viz-table wi-table tf-table">
                  <thead>
                    <tr><th>#</th><th>Transit</th><th>Services · via</th><th className="r">Sailings / wk</th><th className="r">Port cost / TEU</th><th className="r">Plan TEU / wk</th></tr>
                  </thead>
                  <tbody>
                    {rows.slice(0, ROWS_SHOWN).map((r, i) => (
                      <tr key={i} aria-selected={i === pick} className={i === pick ? 'tf-on' : ''} tabIndex={0}
                        onClick={() => setPick(i)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setPick(i); } }}>
                        <td>{i + 1}</td>
                        <td>
                          <span className="rl-bar tf-bar"><span style={{ width: `${(r.transit_days / slowest) * 100}%` }} /></span>
                          <span className="rl-val">{days(r.transit_days)}</span>
                          {r.within_limit === false && <span className="dz-pct tf-over" title="Slower than the OD's transit-time limit: the engine would not offer it"> · over limit</span>}
                        </td>
                        <td>
                          {r.segments.map((s) => s.service).join(' → ')}
                          <div className="dz-pct">{r.transfers === 0 ? 'direct' : `via ${r.hubs.join(', ')}`}{r.max_wait_days > 0 ? ` · up to ${days(r.max_wait_days)} waiting for connections` : ''}</div>
                        </td>
                        <td className="r">{r.departures_per_week}</td>
                        <td className="r">{fmtUsd(r.port_cost_per_teu)}</td>
                        <td className="r">{dm ? (r.plan_teu > 0 ? fmtNum(Math.round(r.plan_teu)) : '—') : 'n/a'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {rows.length > ROWS_SHOWN && <div className="viz-note px-3 pb-2">{data.itineraries_found - ROWS_SHOWN} slower itineraries not shown.</div>}
            </InstrumentPanel>
          </div>
          <div className="col-span-12 xl:col-span-5 min-w-0 space-y-3">
            {sel && <ItineraryDetail sel={sel} rank={pick + 1} dwell={data.transfer_dwell_days} />}
          </div>
          <div className="col-span-12 min-w-0">
            <InstrumentPanel title={`Itinerary ${pick + 1} on the map`} right={<span className="text-[12px] text-slate-400">coloured = legs ridden · faint = the rest of those services</span>} bodyPadding="flush">
              <div style={{ height: 440 }}>
                <WorldMap optimizationState={optimizationState} selectedServices={mapServices} itinerary={itinerary} dataset={data?.dataset}
                  drawKey={`transit|${data.origin}|${data.destination}|${pick}`} />
              </div>
            </InstrumentPanel>
          </div>
        </div>
      )}

      <Provenance
        source="POST /api/transit → src/network/paths.build_paths (+ the flow LP of the What-if baseline for routed TEU)"
        sourceStatus={state.status === 'ok' ? 'available' : 'no_data'}
        attribution="Read-only view of the recorded plan"
        license="Internal artifact"
      />
    </div>
  );
}

function PortSelect({ id, label, value, onChange, ports }) {
  return (
    <div className="tf-port">
      <label htmlFor={id} className="dz-label">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Pick a port…</option>
        {ports.map((p) => <option key={p.code} value={p.code}>{p.code} · {p.name}</option>)}
      </select>
    </div>
  );
}

const TONES = ['#3987e5', '#d95926', '#c9a227'];

function ItineraryDetail({ sel, rank, dwell }) {
  return (
    <InstrumentPanel title={`Itinerary ${rank}`} right={<span className="text-[12px] text-slate-400">{days(sel.transit_days)} · {sel.transfers === 0 ? 'direct' : `${sel.transfers} transfer${sel.transfers === 1 ? '' : 's'}`}</span>}>
      <ol className="tf-steps">
        {sel.segments.map((s, i) => (
          <li key={i}>
            <span className="tf-dot" style={{ background: TONES[i % TONES.length] }} aria-hidden="true" />
            <div>
              <b>{s.service}</b> <span className="dz-pct">({s.vessel_class}, {s.departures_per_week}× / wk)</span>
              <div>{s.from} → {s.to}: {days(s.ride_days)} on board{s.calls.length > 2 ? `, calling ${s.calls.slice(1, -1).join(', ')}` : ''}</div>
              {i < sel.segments.length - 1 && (
                <div className="dz-pct">Transfer at {s.to}: {days(dwell)} dwell in the transit time; the next {sel.segments[i + 1].service} departure can be up to {days(7 / (sel.segments[i + 1].departures_per_week || 1))} away.</div>
              )}
            </div>
          </li>
        ))}
      </ol>
      <div className="viz-note">
        Transit = time on board (sailing + stays at intermediate calls) + {days(dwell)} per transfer, as the engine counts it.
        Waiting for the first departure and for connections is not in it.
      </div>
    </InstrumentPanel>
  );
}
