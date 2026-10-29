/**
 * DisruptionPanels — the What-if page's closure scenario (#2) and resilience ranking (#4).
 *
 *   ClosureControls     pick a chokepoint closure preset and / or ports to close
 *   DisruptionReport    what the closure did: legs on detours (with the distance source), suspended services
 *   ResilienceRanking   every single passage (or the busiest ports) closed in turn, ranked by weekly profit lost;
 *                       "Apply" loads that case into the what-if above
 *
 * The numbers come from backend/whatif.py + backend/disruption.py + backend/chokepoints.py: the recorded plan,
 * the affected legs re-measured on their detours, cargo re-routed by the flow LP, priced by the ledger.
 */
import React, { useState } from 'react';
import InstrumentPanel from './InstrumentPanel.jsx';
import { fmtNum, fmtUsd } from '../../utils/formatters.js';
import { passageName } from '../../services/seaRoutes.js';
import { fetchResilience, addedPassages } from '../../services/chokepoints.js';

/** Closure presets (the backend's PRESETS; its response carries the authoritative labels and notes). */
export const CLOSURE_PRESETS = [
  { key: 'red_sea', label: 'Red Sea closed' },
  { key: 'suez', label: 'Suez closed' },
  { key: 'panama', label: 'Panama closed' },
  { key: 'hormuz', label: 'Hormuz closed' },
  { key: 'malacca', label: 'Malacca closed' },
  { key: 'gibraltar', label: 'Gibraltar closed' },
  { key: 'bosporus', label: 'Bosporus closed' },
];

const nm = (v) => `${fmtNum(Math.round(v))} nm`;
const signed = (v, f) => `${v > 0 ? '+' : v < 0 ? '−' : '±'}${f(Math.abs(v))}`;
export const closureActive = (c) => Boolean(c.preset || c.closed.length || c.ports.length);

export function ClosureControls({ closure, setClosure, ports = [] }) {
  const [pick, setPick] = useState('');
  const addPort = (code) => { if (code && !closure.ports.includes(code)) setClosure({ ...closure, ports: [...closure.ports, code] }); setPick(''); };
  return (
    <div className="dz-controls">
      <div className="dz-row" role="group" aria-label="Chokepoint closure">
        <span className="dz-label">Close a chokepoint</span>
        {CLOSURE_PRESETS.map((p) => (
          <button key={p.key} type="button" className="cmp-btn" aria-pressed={closure.preset === p.key}
            onClick={() => setClosure({ ...closure, preset: closure.preset === p.key ? null : p.key, closed: [] })}>{p.label}</button>
        ))}
        {closure.closed.map((c) => (
          <button key={c} type="button" className="cmp-btn" aria-pressed="true" title="Remove this closure"
            onClick={() => setClosure({ ...closure, closed: closure.closed.filter((x) => x !== c) })}>{passageName(c)} closed ✕</button>
        ))}
      </div>
      <div className="dz-row">
        <label className="dz-label" htmlFor="dz-port">Close a port</label>
        <select id="dz-port" value={pick} onChange={(e) => addPort(e.target.value)}>
          <option value="">Pick a port the plan calls…</option>
          {ports.map((p) => <option key={p.code} value={p.code}>{p.code} · {p.name} ({p.calls} call{p.calls === 1 ? '' : 's'})</option>)}
        </select>
        {closure.ports.map((p) => (
          <button key={p} type="button" className="cmp-btn" aria-pressed="true" title="Re-open this port"
            onClick={() => setClosure({ ...closure, ports: closure.ports.filter((x) => x !== p) })}>{p} closed ✕</button>
        ))}
        {closureActive(closure) && (
          <button type="button" className="cmp-btn" onClick={() => setClosure({ preset: null, closed: [], ports: [] })}>Re-open everything</button>
        )}
      </div>
    </div>
  );
}

export function DisruptionReport({ report, scen, base }) {
  const legs = report.rerouted_legs || [];
  const sus = report.suspended_services || [];
  const skip = report.services_skipping || [];
  const what = [
    ...(report.closed_passages || []).map(passageName),
    ...(report.closed_ports || []).map((p) => `port ${p}`),
  ].join(', ');
  return (
    <div className="dz-report">
      <p className="dz-lead">
        <b>{report.preset_label || `Closed: ${what}`}.</b>{' '}
        {report.preset_note}
        {!report.preset && report.detour_avoid?.length ? ` Detours may not use: ${report.detour_avoid.map(passageName).join(', ')}.` : ''}
      </p>
      <div className="dz-stats">
        <div><span>Legs on a detour</span><b>{legs.length}</b></div>
        <div><span>Extra sailing</span><b>{signed(report.extra_nm_per_week || 0, (v) => `${fmtNum(Math.round(v))} nm/wk`)}</b></div>
        <div><span>Vessels needed</span><b>{report.vessels_before} → {report.vessels_after}</b></div>
        <div><span>Services suspended</span><b>{sus.length}</b></div>
        {skip.length > 0 && <div><span>Services skipping a port</span><b>{skip.length}</b></div>}
        <div><span>TEU no longer carried</span><b>{fmtNum(Math.max(0, Math.round(base.served_teu - scen.served_teu)))}/wk</b></div>
      </div>
      {!scen.valid && (
        <p className="dz-warn" role="status">
          The disrupted plan breaks a ledger rule ({[...new Set((scen.violations || []).map((v) => v.type))].join(', ') || 'see the engine log'}):
          {' '}the services on screen would need vessels the fleet does not have. Read the figures as a lower bound on the damage.
        </p>
      )}
      {legs.length > 0 && (
        <table className="viz-table wi-table dz-table">
          <thead><tr><th>Leg</th><th className="r">Distance</th><th>Detour adds</th></tr></thead>
          <tbody>
            {legs.slice(0, 12).map((l) => (
              <tr key={`${l.from}-${l.to}`} title={`Services: ${(l.services || []).join(', ') || '—'}
Detour via: ${(l.via_after || []).map(passageName).join(', ') || 'open sea'}
Distance from: ${l.source}`}>
                <td>{l.from} → {l.to}<div className="dz-pct">{(l.services || []).join(', ')}</div></td>
                <td className="r">{nm(l.nm_before)} → {nm(l.nm_after)} <span className="dz-pct">({signed(((l.nm_after - l.nm_before) / l.nm_before) * 100, (v) => `${v.toFixed(0)}%`)})</span></td>
                <td>{addedPassages(l).map(passageName).join(', ') || 'a longer lane'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {legs.length > 12 && <div className="viz-note">{legs.length - 12} more legs on detours.</div>}
      {sus.length > 0 && (
        <ul className="dz-list" aria-label="Suspended services">
          {sus.map((s) => <li key={s.id}><b>{s.id}</b> suspended: {s.reason}</li>)}
        </ul>
      )}
      {skip.length > 0 && (
        <ul className="dz-list" aria-label="Services skipping a closed port">
          {skip.map((s) => <li key={s.id}><b>{s.id}</b> skips {s.skips.join(', ')}</li>)}
        </ul>
      )}
      <div className="viz-note">
        Detour distances: {[...new Set(legs.map((l) => l.source))].join('; ') || '—'} (hover a row for its full route).
        {' '}Method: {report.method}.
      </div>
    </div>
  );
}

export function ResilienceRanking({ run, onApply }) {
  const [target, setTarget] = useState('passages');
  const [state, setState] = useState({ status: 'idle', data: null, error: null, target: null });
  const go = async (t = target) => {
    setState({ status: 'loading', data: null, error: null, target: t });
    try {
      const data = await fetchResilience(run, t, 25);
      setState({ status: 'ok', data, error: null, target: t });
    } catch (e) {
      setState({ status: 'error', data: null, error: String(e?.message || e), target: t });
    }
  };
  const rows = state.data?.rows || [];
  const worst = Math.max(1, ...rows.map((r) => Math.abs(Math.min(0, r.profit_change))));
  return (
    <InstrumentPanel
      title="Resilience ranking"
      right={<span className="text-[12px] text-slate-400">one closure at a time · Δ weekly profit</span>}
    >
      <div className="dz-row" role="group" aria-label="What to close">
        <div className="rl-tabs" role="radiogroup" aria-label="Rank">
          {[['passages', 'Chokepoints the plan crosses'], ['ports', 'The 25 most-called ports']].map(([k, label]) => (
            <button key={k} type="button" role="radio" aria-checked={target === k} className="cmp-btn" aria-pressed={target === k}
              onClick={() => setTarget(k)}>{label}</button>
          ))}
        </div>
        <button type="button" className="cmp-btn dz-run" onClick={() => go()} disabled={state.status === 'loading'}>
          {state.status === 'loading' ? 'Ranking…' : `Rank ${target === 'passages' ? 'chokepoints' : 'ports'}`}
        </button>
      </div>
      {state.status === 'idle' && (
        <p className="text-[12px] text-slate-400 mt-2 max-w-[80ch]">
          Closes each chokepoint the plan crosses (or each of its 25 busiest ports) in turn, re-routes the cargo over what is
          left with the flow LP and prices it with the ledger. About a second per case.
        </p>
      )}
      {state.status === 'error' && <p className="dz-warn mt-2">Ranking failed: {state.error}</p>}
      {state.status === 'ok' && (
        <>
          <table className="viz-table wi-table rl-table mt-2">
            <thead><tr><th>#</th><th>Closed</th><th>Δ profit / wk</th><th className="r">Δ TEU / wk</th><th className="r">Δ vessels</th><th>Suspended</th><th><span className="sr-only">Apply</span></th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.id}>
                  <td>{i + 1}</td>
                  <td>{state.target === 'passages' ? passageName(r.id) : r.id}{r.calls ? <span className="dz-pct"> · {r.calls} calls</span> : null}{!r.valid && <span className="dz-pct" title="The disrupted plan breaks a ledger rule (fleet inventory)"> · rule broken</span>}</td>
                  <td>
                    <span className="rl-bar"><span style={{ width: `${(Math.abs(Math.min(0, r.profit_change)) / worst) * 100}%` }} /></span>
                    <span className="rl-val">{signed(r.profit_change, fmtUsd)}</span>
                  </td>
                  <td className="r">{signed(Math.round(r.served_change), fmtNum)}</td>
                  <td className="r">{signed(r.vessels_change, String)}</td>
                  <td>{r.suspended.length ? r.suspended.length : '—'}</td>
                  <td><button type="button" className="cmp-btn" onClick={() => onApply(state.target, r.id)} title="Load this closure into the what-if above">Apply</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="viz-note">
            Baseline {fmtUsd(state.data.baseline.profit)}/wk, {fmtNum(Math.round(state.data.baseline.served_teu))} TEU/wk, {state.data.baseline.vessels} vessels.
            {' '}{rows.length} cases in {state.data.runtime_sec} s. Method: {state.data.method}.
          </div>
        </>
      )}
    </InstrumentPanel>
  );
}
