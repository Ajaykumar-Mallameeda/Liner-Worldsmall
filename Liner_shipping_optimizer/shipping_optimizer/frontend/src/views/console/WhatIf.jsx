/**
 * WhatIf.jsx — re-price the plan on screen under a different fuel price or demand level, without re-running
 * the optimizer (POST /api/whatif, backend/whatif.py).
 *
 * Fixed: the run's services, weekly departures and vessels (so vessel hire and port-call costs do not move).
 * Moved: every OD's weekly TEU × demand multiplier; bunker price × fuel multiplier. The cargo is re-routed by
 * the engine's flow LP over every valid path through the operated services and priced by the engine's ledger.
 * The same evaluation at 1× / 1× is the baseline the scenario is compared with; the recorded figure is shown
 * beside it (the re-evaluation can route a little better than the recorded flows).
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Provenance } from '../../components/console/p12.jsx';
import { getSelectedRun, subscribeRun, runLabel } from '../../services/runSelection.js';
import { fmtNum, fmtPct, fmtUsd } from '../../utils/formatters.js';

const DEBOUNCE_MS = 350;
const PRESETS = [
  { label: 'Fuel +50%', d: 1, f: 1.5 },
  { label: 'Fuel −30%', d: 1, f: 0.7 },
  { label: 'Demand +20%', d: 1.2, f: 1 },
  { label: 'Demand −20%', d: 0.8, f: 1 },
  { label: 'Downturn (demand −20%, fuel +30%)', d: 0.8, f: 1.3 },
];
const COST_LINES = [
  ['vessel_cost', 'Vessel hire', 'fixed'],
  ['fuel_cost', 'Fuel', 'price × tonnes'],
  ['port_call_fixed_cost', 'Port calls', 'fixed'],
  ['handling_cost', 'Handling', 'per TEU'],
  ['transshipment_cost', 'Transshipment', 'per TEU'],
  ['port_variable_cost', 'Port variable', 'per TEU'],
];
const MOVERS_SHOWN = 8;

const sign = (v, f = fmtUsd) => (v == null ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : '±'}${f(Math.abs(v))}`);
const xLabel = (m) => `${m.toFixed(2)}×`;

function Slider({ id, label, value, min, max, step, onChange, hint }) {
  return (
    <div className="wi-slider">
      <div className="wi-slider-head">
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id}>{xLabel(value)} <span>({value >= 1 ? '+' : '−'}{Math.abs(Math.round((value - 1) * 100))}%)</span></output>
      </div>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <div className="wi-slider-scale"><span>{xLabel(min)}</span><span>{hint}</span><span>{xLabel(max)}</span></div>
    </div>
  );
}

function Kpi({ k, base, scen, fmt = fmtUsd, deltaFmt, good = 'up' }) {
  const d = scen != null && base != null ? scen - base : null;
  const tone = d == null || Math.abs(d) < 1e-9 ? '' : (d > 0) === (good === 'up') ? 'is-good' : 'is-bad';
  return (
    <div className="wi-kpi">
      <div className="k">{k}</div>
      <div className="v">{scen != null ? fmt(scen) : '—'}</div>
      <div className={`d ${tone}`}>{d == null ? '' : deltaFmt ? deltaFmt(d) : sign(d, fmt)} <span>vs {base != null ? fmt(base) : '—'}</span></div>
    </div>
  );
}

export default function WhatIf() {
  const [run, setRun] = useState(getSelectedRun());
  useEffect(() => subscribeRun(setRun), []);
  const [demandM, setDemandM] = useState(1);
  const [fuelM, setFuelM] = useState(1);
  const [state, setState] = useState({ status: 'idle', data: null, error: null });
  const reqId = useRef(0);

  useEffect(() => {
    const id = ++reqId.current;
    setState((s) => ({ ...s, status: 'loading' }));
    const t = setTimeout(async () => {
      try {
        const r = await fetch('/api/whatif', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run, demand_multiplier: demandM, fuel_multiplier: fuelM }),
        });
        const body = await r.json().catch(() => null);
        if (id !== reqId.current) return;
        if (!r.ok || !body?.scenario) {
          const unreachable = !body || r.status === 500 && !body?.detail;
          setState({ status: unreachable ? 'unavailable' : 'error', data: null, error: body?.detail || `HTTP ${r.status}` });
          return;
        }
        setState({ status: 'ok', data: body, error: null });
      } catch (e) {
        if (id === reqId.current) setState({ status: 'unavailable', data: null, error: String(e?.message || e) });
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [run, demandM, fuelM]);

  const data = state.data;
  const base = data?.baseline;
  const scen = data?.scenario;
  const movers = useMemo(() => {
    if (!base || !scen) return [];
    const b = new Map(base.per_service.map((s) => [s.id, s]));
    return scen.per_service.map((s) => {
      const o = b.get(s.id) || { profit: 0, revenue: 0, leg_load_factor: null };
      return { id: s.id, base: o.profit, scen: s.profit, d: s.profit - o.profit, lfB: o.leg_load_factor, lfS: s.leg_load_factor };
    }).sort((x, y) => Math.abs(y.d) - Math.abs(x.d)).slice(0, MOVERS_SHOWN);
  }, [base, scen]);
  const maxMove = Math.max(1, ...movers.map((m) => Math.abs(m.d)));
  const lossBase = base ? base.per_service.filter((s) => s.profit < 0).length : 0;
  const lossScen = scen ? scen.per_service.filter((s) => s.profit < 0).length : 0;
  const atBase = demandM === 1 && fuelM === 1;
  const busy = state.status === 'loading';

  return (
    <div className="cx-page-body space-y-3">
      <PageHead
        section="Scenarios"
        eyebrow="What-if"
        title="What-if: fuel price and demand"
        subtitle="Re-price the plan on screen without re-running the optimizer. Services, departures and vessels stay as planned; cargo is re-routed over the same network by the engine's flow LP and priced by its ledger."
        pills={[
          { tone: 'selected', label: runLabel(run, typeof data?.dataset === 'string' ? data.dataset : data?.dataset?.key) },
          { tone: state.status === 'ok' ? 'available' : state.status === 'loading' ? 'active' : 'no_data', label: state.status === 'ok' ? `LP ${scen.lp_sec.toFixed(1)} s` : state.status === 'loading' ? 're-routing…' : state.status === 'unavailable' ? 'needs backend' : state.status },
        ]}
      />

      <InstrumentPanel title="Scenario" right={<span className="text-[12px] text-slate-400">applies to the run selected in the header</span>}>
        <div className="wi-controls">
          <Slider id="wi-fuel" label="Bunker fuel price" value={fuelM} min={0.5} max={3} step={0.05} onChange={setFuelM} hint="× recorded price" />
          <Slider id="wi-demand" label="Demand (every lane)" value={demandM} min={0.5} max={2} step={0.05} onChange={setDemandM} hint="× weekly TEU" />
        </div>
        <div className="wi-presets" role="group" aria-label="Scenario presets">
          {PRESETS.map((p) => (
            <button key={p.label} type="button" className="cmp-btn" aria-pressed={demandM === p.d && fuelM === p.f}
              onClick={() => { setDemandM(p.d); setFuelM(p.f); }}>{p.label}</button>
          ))}
          <button type="button" className="cmp-btn" disabled={atBase} onClick={() => { setDemandM(1); setFuelM(1); }}>Reset to plan</button>
        </div>
      </InstrumentPanel>

      {state.status === 'unavailable' && (
        <InstrumentPanel title="Re-evaluation unavailable">
          <p className="text-[12px] text-slate-300 max-w-[70ch]">
            The what-if needs the backend: it re-solves the flow LP and prices the result with the engine's ledger in Python.
            Start it (for example <code>uvicorn backend.server:app --port 8000</code>) and this page updates.
          </p>
        </InstrumentPanel>
      )}
      {state.status === 'error' && (
        <InstrumentPanel title="This run cannot be re-evaluated">
          <p className="text-[12px] text-slate-300">{state.error}</p>
        </InstrumentPanel>
      )}

      {base && scen && (
        <div className={`space-y-3 ${busy ? 'wi-stale' : ''}`} aria-busy={busy}>
          <div className="wi-kpis">
            <Kpi k="Weekly profit" base={base.profit} scen={scen.profit} />
            <Kpi k="Margin" base={base.margin_pct} scen={scen.margin_pct} fmt={(v) => fmtPct(v)} deltaFmt={(d) => `${d >= 0 ? '+' : '−'}${Math.abs(d).toFixed(1)} pp`} />
            <Kpi k="Revenue" base={base.revenue} scen={scen.revenue} />
            <Kpi k="Total cost" base={base.total_cost} scen={scen.total_cost} good="down" />
            <Kpi k="Coverage" base={base.coverage_pct} scen={scen.coverage_pct} fmt={(v) => fmtPct(v)} deltaFmt={(d) => `${d >= 0 ? '+' : '−'}${Math.abs(d).toFixed(1)} pp`} />
            <Kpi k="TEU carried / wk" base={base.served_teu} scen={scen.served_teu} fmt={fmtNum} deltaFmt={(d) => sign(d, fmtNum)} />
          </div>

          <div className="grid grid-cols-12 gap-3">
            <div className="col-span-12 xl:col-span-7 min-w-0">
              <InstrumentPanel title="Weekly cost lines" right={<span className="text-[12px] text-slate-400">baseline → scenario</span>}>
                <table className="viz-table wi-table">
                  <thead><tr><th>Line</th><th>Moves with</th><th className="r">Baseline</th><th className="r">Scenario</th><th className="r">Change</th></tr></thead>
                  <tbody>
                    <tr className="is-total"><td>Revenue</td><td>TEU carried</td><td className="r">{fmtUsd(base.revenue)}</td><td className="r">{fmtUsd(scen.revenue)}</td><td className="r">{sign(scen.revenue - base.revenue)}</td></tr>
                    {COST_LINES.map(([k, label, how]) => (
                      <tr key={k}><td>{label}</td><td>{how}</td><td className="r">{fmtUsd(base[k])}</td><td className="r">{fmtUsd(scen[k])}</td><td className="r">{sign(scen[k] - base[k])}</td></tr>
                    ))}
                    <tr className="is-total"><td>Total cost</td><td /><td className="r">{fmtUsd(base.total_cost)}</td><td className="r">{fmtUsd(scen.total_cost)}</td><td className="r">{sign(scen.total_cost - base.total_cost)}</td></tr>
                    <tr className="is-total"><td>Profit</td><td /><td className="r">{fmtUsd(base.profit)}</td><td className="r">{fmtUsd(scen.profit)}</td><td className="r">{sign(scen.profit - base.profit)}</td></tr>
                  </tbody>
                </table>
                <div className="viz-note">
                  Recorded run: profit {fmtUsd(data.recorded.profit)}/wk, coverage {data.recorded.coverage_pct != null ? fmtPct(data.recorded.coverage_pct) : '—'}.
                  {' '}The baseline re-routes the same plan at 1× / 1× ({sign(base.profit - (data.recorded.profit ?? base.profit))} vs recorded), so the change above is the scenario's alone.
                  {' '}Demand {fmtNum(scen.demand_teu)} TEU/wk, unserved {fmtNum(scen.unserved_teu)}; loss-making services {lossBase} → {lossScen}.
                </div>
              </InstrumentPanel>
            </div>
            <div className="col-span-12 xl:col-span-5 min-w-0">
              <InstrumentPanel title="Services that move most" right={<span className="text-[12px] text-slate-400">Δ weekly profit</span>}>
                {atBase ? (
                  <div className="text-[12px] text-slate-400 p-1">Move a slider or pick a preset to see which services gain or lose.</div>
                ) : (
                  <ul className="wi-movers">
                    {movers.map((m) => (
                      <li key={m.id} title={`${m.id}: ${fmtUsd(m.base)} → ${fmtUsd(m.scen)}; leg load factor ${m.lfB != null ? fmtPct(m.lfB * 100) : '—'} → ${m.lfS != null ? fmtPct(m.lfS * 100) : '—'}`}>
                        <span className="id">{m.id}</span>
                        <span className="wi-div" aria-hidden="true">
                          <span className={m.d < 0 ? 'neg' : 'pos'} style={{ width: `${(Math.abs(m.d) / maxMove) * 50}%` }} />
                        </span>
                        <span className="val">{sign(m.d)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </InstrumentPanel>
            </div>
          </div>

          <div className="viz-note">
            Method: {data.model.method}. {data.model.services} services, {fmtNum(data.model.path_columns)} path columns (≤ {data.model.max_transfers} transfers), dataset {data.dataset?.label || data.dataset?.key || String(data.dataset)}.
            {' '}Fuel scales exactly (fuel cost = departures × tonnes × price). Demand changes re-route cargo inside fixed capacity, so revenue does not grow in proportion once legs are full. Nothing here re-runs the GA or the MILP.
          </div>
        </div>
      )}

      <Provenance
        source="POST /api/whatif → src/network/flow LP + src/network/ledger.compute_ledger"
        sourceStatus={state.status === 'ok' ? 'available' : 'no_data'}
        attribution="Read-only re-evaluation of the recorded plan"
        license="Internal artifact"
      />
    </div>
  );
}
