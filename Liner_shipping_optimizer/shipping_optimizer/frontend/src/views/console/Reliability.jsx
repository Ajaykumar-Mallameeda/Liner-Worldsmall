/**
 * Reliability.jsx — schedule reliability and port congestion by Monte Carlo (2026-10-29, feature #7).
 *
 * POST /api/reliability (backend/reliability.py) on the run selected in the header: every service sails its pro-forma
 * rotation many times with random holds at its calls, recovers by speeding up to its class's max speed, absorbs the
 * rest in its buffer and blanks a sailing when a whole slot behind. The hold probability and length are fitted to a
 * published market level (Sea-Intelligence), so the plan's services, ports and cargo differ by their own structure.
 * Ports can be marked congested (more frequent holds) to see what that costs.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Provenance } from '../../components/console/p12.jsx';
import { SourceChip } from '../../components/common/Figure.jsx';
import { getSelectedRun, subscribeRun, runLabel } from '../../services/runSelection.js';
import { getPortName } from '../../utils/portLookup.js';
import { fmtNum } from '../../utils/formatters.js';

const DEBOUNCE_MS = 400;
const DEFAULT_TARGET = { on: 62.6, late: 5.31 };
const BIN_VARS = ['--rel-0', '--rel-1', '--rel-2', '--rel-3', '--rel-4'];
const pp = (a, b) => { const d = a - b; return `${d > 0 ? '+' : d < 0 ? '−' : '±'}${Math.abs(d).toFixed(1)} pp`; };

export default function Reliability() {
  const [run, setRun] = useState(getSelectedRun());
  useEffect(() => subscribeRun(setRun), []);
  const [target, setTarget] = useState(DEFAULT_TARGET);
  const [congested, setCongested] = useState([]);
  const [factor, setFactor] = useState(3);
  const [state, setState] = useState({ status: 'idle', data: null, error: null });
  const reqId = useRef(0);
  const [odView, setOdView] = useState('worst');

  useEffect(() => { setCongested([]); }, [run]);
  useEffect(() => {
    const id = ++reqId.current;
    setState((x) => ({ ...x, status: 'loading' }));
    const t = setTimeout(async () => {
      try {
        const r = await fetch('/api/reliability', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run, target_on_time_pct: target.on, target_late_days: target.late, congested_ports: congested, congestion_factor: factor }) });
        const b = await r.json().catch(() => null);
        if (id !== reqId.current) return;
        if (!r.ok || !b?.plan) setState({ status: !b ? 'unavailable' : 'error', data: null, error: b?.detail ? JSON.stringify(b.detail) : `HTTP ${r.status}` });
        else setState({ status: 'ok', data: b, error: null });
      } catch (e) {
        if (id === reqId.current) setState({ status: 'unavailable', data: null, error: String(e?.message || e) });
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [run, target, congested, factor]);

  const d = state.data;
  const plan = d?.plan;
  const sc = d?.scenario || null;
  const view = sc || plan;
  const toggle = (port) => setCongested((c) => (c.includes(port) ? c.filter((x) => x !== port) : c.length < 20 ? [...c, port] : c));
  const scPorts = useMemo(() => Object.fromEntries((sc?.ports || []).map((p) => [p.port, p])), [sc]);
  const scSvcs = useMemo(() => Object.fromEntries((sc?.services || []).map((s) => [s.id, s])), [sc]);
  const ods = useMemo(() => {
    const L = [...(view?.ods || [])];
    if (odView === 'teu') L.sort((a, b) => b.teu - a.teu);
    return L.slice(0, 25);
  }, [view, odView]);
  const cal = d?.calibration;

  return (
    <div className="cx-page-body space-y-3">
      <PageHead
        section="Scenarios"
        eyebrow="Reliability"
        title="Schedule reliability and port congestion"
        subtitle="How punctual the plan's services, ports and cargo would be at today's market level of disruption, simulated rotation by rotation — and what congestion at chosen ports costs. Delay is measured against each service's pro-forma schedule."
        pills={[
          { tone: 'selected', label: runLabel(run, d?.dataset) },
          { tone: state.status === 'ok' ? 'available' : state.status === 'loading' ? 'active' : 'no_data',
            label: state.status === 'ok' ? `${view.on_time_pct}% of calls on time${sc ? ' (congested)' : ''}` : state.status === 'loading' ? 'simulating…' : state.status === 'unavailable' ? 'needs backend' : state.status },
        ]}
      />

      <InstrumentPanel title="Assumptions" right={<span className="text-[12px] text-slate-400">applies to the run selected in the header</span>}>
        <div className="em-controls">
          <Slider id="rel-on" label="Market calls on time (calibration target)" value={target.on} min={30} max={90} step={0.1}
            onChange={(v) => setTarget((t) => ({ ...t, on: v }))} fmt={(v) => `${v.toFixed(1)}%`}
            hint={<>Sea-Intelligence global schedule reliability, June 2026: 62.6% (arrival within 1 day of schedule)</>} />
          <Slider id="rel-late" label="Late vessels: average delay (target)" value={target.late} min={1.5} max={12} step={0.01}
            onChange={(v) => setTarget((t) => ({ ...t, late: v }))} fmt={(v) => `${v.toFixed(2)} d`}
            hint="Sea-Intelligence, June 2026: 5.31 days" />
          <Slider id="rel-factor" label="Congestion: holds at a congested port" value={factor} min={1} max={10} step={0.5}
            onChange={setFactor} fmt={(v) => `${v}× as often`} disabled={!congested.length}
            hint={congested.length ? `Congested: ${congested.join(', ')}` : 'Mark ports congested in the Ports table below'} />
        </div>
        <div className="rel-actions">
          {(target.on !== DEFAULT_TARGET.on || target.late !== DEFAULT_TARGET.late) && <button type="button" className="cmp-btn" onClick={() => setTarget(DEFAULT_TARGET)}>Reset to June 2026</button>}
          {congested.length > 0 && <button type="button" className="cmp-btn" onClick={() => setCongested([])}>Clear congestion</button>}
          {cal && (
            <span className={`dz-pct${cal.matched ? '' : ' tf-over'}`}>
              Fitted: a hold at {(cal.p * 100).toFixed(1)}% of calls, {cal.mu_days.toFixed(2)} days on average (exponential)
              {cal.matched ? ` · the plan then sees ${cal.on_time * 100 > 0 ? (cal.on_time * 100).toFixed(1) : '—'}% on time, ${cal.late_days.toFixed(2)} d late` : ' · target not reachable with this plan — read as indicative'}
            </span>
          )}
        </div>
      </InstrumentPanel>

      {state.status === 'loading' && !d && <p className="text-[12px] text-slate-400">Simulating every service and fitting the disruption level: a few seconds the first time per run and target.</p>}
      {state.status === 'unavailable' && <p className="dz-warn">Needs the backend (POST /api/reliability). {state.error}</p>}
      {state.status === 'error' && <p className="dz-warn">Simulation failed: {state.error}</p>}

      {d && (
        <div className={state.status === 'loading' ? 'rel-busy' : ''} aria-busy={state.status === 'loading'}>
          <div className="em-kpis">
            <Kpi label="Calls on time" src="Simulation, calibrated" def="arrival ≤ 1 day late (Sea-Intelligence)" value={`${view.on_time_pct}%`} sub={sc ? `${pp(sc.on_time_pct, plan.on_time_pct)} vs no congestion` : 'equals the target by calibration'} />
            <Kpi label="Late calls: average delay" src="Simulation, calibrated" def="mean delay of calls > 1 day late" value={`${view.late_days.toFixed(2)} d`} sub={sc ? `${plan.late_days.toFixed(2)} d without congestion` : null} />
            <Kpi label="Sailings blanked to recover" src="Simulation" def="departures skipped to re-phase" value={`${view.blank_sailings_pct}%`} sub={sc ? `${plan.blank_sailings_pct}% without congestion` : 'vessel a whole slot behind: re-phased'} />
            <Kpi label="Cargo on time" src="Simulation" def="TEU at destination ≤ 1 day late" value={`${view.cargo.on_time_pct}%`} sub={sc ? `${pp(sc.cargo.on_time_pct, plan.cargo.on_time_pct)} · TEU-weighted` : `direct ${view.cargo.direct_on_time_pct}% · transhipped ${view.cargo.transhipped_on_time_pct ?? '—'}%`} />
            <Kpi label="Transhipped TEU missing a connection" src="Simulation" def="transhipped TEU missing the planned onward sailing" value={`${view.cargo.missed_connection_pct}%`} sub={`${fmtNum(Math.round(view.cargo.transhipped_teu))} of ${fmtNum(Math.round(view.cargo.teu))} TEU/wk transhipped`} />
          </div>

          <InstrumentPanel title="Cargo delay at destination" right={<span className="text-[12px] text-slate-400">share of TEU per week, vs the pro-forma plan</span>}>
            <DelayBars rows={[['Plan', plan.cargo.histogram], ...(sc ? [[`Congested ×${factor}`, sc.cargo.histogram]] : [])]} />
          </InstrumentPanel>

          <InstrumentPanel title="Services" right={<span className="text-[12px] text-slate-400">least punctual first</span>} bodyPadding="flush">
            <div className="tf-scroll">
              <table className="viz-table wi-table tf-table rel-table">
                <thead><tr><th>Service</th><th className="r">Calls on time</th><th className="r">Late: avg</th><th className="r">90% of calls within</th><th className="r">Buffer</th><th className="r">Speed headroom</th><th className="r">Blank sailings / yr</th><th>Least punctual call</th></tr></thead>
                <tbody>
                  {plan.services.map((s) => {
                    const x = scSvcs[s.id];
                    return (
                      <tr key={s.id}>
                        <td>{s.id}<div className="dz-pct">{s.vessels} vessels · {s.calls} calls · {s.departures_per_week}× / wk</div></td>
                        <td className="r"><Bar pct={s.on_time_pct} />{x && <div className="dz-pct">{x.on_time_pct}% congested</div>}</td>
                        <td className="r">{s.late_days.toFixed(1)} d</td>
                        <td className="r">{s.p90_delay_days.toFixed(1)} d</td>
                        <td className="r">{s.buffer_days.toFixed(1)} d</td>
                        <td className="r">{s.recover_pct}%<div className="dz-pct">{s.speed_knots} → {s.max_speed_knots} kn</div></td>
                        <td className="r">{s.blank_sailings_per_year}</td>
                        <td>{s.worst_call}<div className="dz-pct">{s.worst_call_on_time_pct}% on time</div></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </InstrumentPanel>

          <InstrumentPanel title="Ports" right={<span className="text-[12px] text-slate-400">least punctual departures first · mark a port congested to test it</span>} bodyPadding="flush">
            <div className="tf-scroll">
              <table className="viz-table wi-table tf-table rel-table">
                <thead><tr><th>Port</th><th className="r">Calls / wk</th><th className="r">Arrivals on time</th><th className="r">Departures on time</th><th className="r">Late arrivals: avg</th><th>Congestion</th></tr></thead>
                <tbody>
                  {plan.ports.map((p) => {
                    const x = scPorts[p.port];
                    const on = congested.includes(p.port);
                    return (
                      <tr key={p.port}>
                        <td>{p.port}<div className="dz-pct">{getPortName(p.port)}</div></td>
                        <td className="r">{p.calls_per_week}</td>
                        <td className="r">{p.on_time_pct}%{x && <div className="dz-pct">{x.on_time_pct}% congested</div>}</td>
                        <td className="r">{p.departure_on_time_pct}%{x && <div className={`dz-pct${x.departure_on_time_pct < p.departure_on_time_pct - 1 ? ' tf-over' : ''}`}>{x.departure_on_time_pct}% congested</div>}</td>
                        <td className="r">{p.late_days.toFixed(1)} d</td>
                        <td><button type="button" className="cmp-btn" aria-pressed={on} onClick={() => toggle(p.port)}>{on ? 'Congested' : 'Congest'}</button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </InstrumentPanel>

          <InstrumentPanel title={`Cargo by origin-destination${sc ? ' (congested)' : ''}`}
            right={(
              <div className="rl-tabs" role="tablist" aria-label="Sort">
                {[['worst', 'Least punctual'], ['teu', 'Largest']].map(([k, label]) => (
                  <button key={k} type="button" role="tab" aria-selected={odView === k} aria-pressed={odView === k} className="cmp-btn" onClick={() => setOdView(k)}>{label}</button>
                ))}
              </div>
            )} bodyPadding="flush">
            <div className="tf-scroll">
              <table className="viz-table wi-table tf-table rel-table">
                <thead><tr><th>Origin → destination</th><th className="r">TEU / wk</th><th className="r">On time</th><th className="r">Missed a connection</th><th className="r">90% within</th><th>Via</th></tr></thead>
                <tbody>
                  {ods.map((o) => (
                    <tr key={`${o.origin}-${o.destination}`}>
                      <td>{o.origin} → {o.destination}<div className="dz-pct">{getPortName(o.origin)} → {getPortName(o.destination)}</div></td>
                      <td className="r">{fmtNum(Math.round(o.teu))}</td>
                      <td className="r"><Bar pct={o.on_time_pct} /></td>
                      <td className="r">{o.via.length ? `${o.missed_connection_pct}%` : '—'}</td>
                      <td className="r">{o.p90_delay_days.toFixed(1)} d late</td>
                      <td>{o.via.length ? o.via.join(', ') : <span className="dz-pct">direct</span>}{o.paths > 1 && <div className="dz-pct">{o.paths} paths</div>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="viz-note px-3 pb-3">Top 25 of {fmtNum(view.ods.length)} origin-destination pairs the flow LP routes. On time = at the destination within 1 day of the pro-forma plan.</p>
          </InstrumentPanel>

          <InstrumentPanel title="Method">
            <ul className="viz-note ws-method">
              <li>Each service sails its pro-forma rotation ({d.settings.chains} vessel chains × {d.settings.measured_rotations} round voyages after {d.settings.warm_rotations} warm-up voyages, seed {d.settings.seed}). At each call a hold may occur (berth congestion, weather, port productivity): with probability p, exponential with mean μ.</li>
              <li>A late vessel recovers on each leg by sailing up to its class's LINERLIB max speed; the buffer at the first port (round voyage − sailing − port stays) absorbs the rest; a vessel still a whole departure interval behind is re-phased into the next slot (a blank sailing), and the cargo of that sailing waits for the next departure.</li>
              <li>p and μ are fitted so this plan's calls reproduce the target market level; the plan's thin buffers then show as blank sailings rather than chronic lateness. Congested ports hold vessels {factor}× as often with the same p and μ.</li>
              <li>Cargo rides its routed path; at a transhipment port it needs {d.settings.transshipment_min_hours} h and boards the first departure after that, or the next one, 7 / frequency days later. Services are simulated independently; fuel spent catching up is not priced here.</li>
            </ul>
          </InstrumentPanel>
        </div>
      )}

      <Provenance
        source="POST /api/reliability → backend/reliability.py (engine service models, flow LP paths, LINERLIB max speeds)"
        sourceStatus={state.status === 'ok' ? 'available' : 'no_data'}
        attribution="Calibration target: Sea-Intelligence Global Liner Performance, June 2026 (62.6% on time, 5.31 days for late arrivals)"
        license="Simulation of the recorded plan; market figures © Sea-Intelligence, cited"
      />
    </div>
  );
}

function Slider({ id, label, value, min, max, step, onChange, fmt, hint, disabled }) {
  return (
    <div className={`em-slider${disabled ? ' is-off' : ''}`}>
      <label htmlFor={id} className="dz-label">{label}</label>
      <div className="em-slider-row">
        <input id={id} type="range" min={min} max={max} step={step} value={value} disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))} aria-valuetext={fmt(value)} />
        <output htmlFor={id}>{fmt(value)}</output>
      </div>
      {hint && <div className="dz-pct em-hint">{hint}</div>}
    </div>
  );
}

function Kpi({ label, value, sub, src, def }) {
  return <div className="em-kpi"><span>{label}</span><b>{value}</b>{sub && <i>{sub}</i>}<SourceChip src={src} def={def} /></div>;
}

function Bar({ pct }) {
  return (
    <span className="rel-cell">
      <span className="rl-bar"><span style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></span>
      <span className="rl-val">{pct}%</span>
    </span>
  );
}

function DelayBars({ rows }) {
  const labels = rows[0][1].map((b) => b.label);
  return (
    <div className="rel-bars">
      {rows.map(([name, hist]) => (
        <div key={name} className="rel-bar-row">
          <span className="rel-bar-name">{name}</span>
          <div className="rel-stack" role="img" aria-label={`${name}: ${hist.map((b) => `${b.label} ${b.share_pct}%`).join(', ')}`}>
            {hist.map((b, i) => (b.share_pct > 0 ? (
              <span key={b.label} style={{ flexGrow: b.share_pct, background: `var(${BIN_VARS[i]})` }} className={i >= 3 ? 'rel-ink-light' : ''} title={`${b.label}: ${b.share_pct}%`}>
                {b.share_pct >= 7 ? `${b.share_pct.toFixed(0)}%` : ''}
              </span>
            ) : null))}
          </div>
        </div>
      ))}
      <div className="em-gradelegend">
        {labels.map((l, i) => <span key={l}><span className="ws-dot" style={{ background: `var(${BIN_VARS[i]})` }} aria-hidden="true" /> {l}</span>)}
      </div>
    </div>
  );
}
