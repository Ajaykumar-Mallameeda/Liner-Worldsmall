/**
 * WhatIf.jsx — re-price the plan on screen under a different fuel price or demand level, without re-running
 * the optimizer (POST /api/whatif, backend/whatif.py).
 *
 * Fixed: the run's services, weekly departures and vessels (so vessel hire and port-call costs do not move).
 * Moved: every OD's weekly TEU × demand multiplier; bunker price × fuel multiplier. The cargo is re-routed by
 * the engine's flow LP over every valid path through the operated services and priced by the engine's ledger.
 * The same evaluation at 1× / 1× is the baseline the scenario is compared with; the recorded figure is shown
 * beside it (the re-evaluation can route a little better than the recorded flows).
 *
 * Closures (2026-10-28): a chokepoint preset (Red Sea, Suez, Panama, ...) and / or closed ports. Legs through a
 * closed passage sail their detour (backend/disruption.py), services with no open lane are suspended, and the map
 * shows the detours. The resilience ranking closes each passage or busy port in turn (backend/chokepoints.py).
 *
 * Market inputs (2026-10-29, components/console/MarketPanels.jsx): freight rate level or Drewry WCI lanes (#20),
 * bunker prices by port from Ship & Bunker (#21), war-risk premiums for JWC listed areas (#19).
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Provenance } from '../../components/console/p12.jsx';
import { SourceChip } from '../../components/common/Figure.jsx';
import { useScenarioIntent } from '../../services/scenarioIntent.js';
import { getSelectedRun, subscribeRun, runLabel, runKey } from '../../services/runSelection.js';
import { fmtNum, fmtPct, fmtUsd } from '../../utils/formatters.js';
import { getPortName } from '../../utils/portLookup.js';
import WorldMap from '../../components/map/WorldMap.jsx';
import { ClosureControls, DisruptionReport, ResilienceRanking, CLOSURE_PRESETS, closureActive } from '../../components/console/DisruptionPanels.jsx';
import { MarketControls, FreightLanes, BunkerReport, WarRiskReport, NO_MARKET, marketActive, marketPayload } from '../../components/console/MarketPanels.jsx';

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
  ['war_risk_cost', 'War-risk premiums', 'per listed-area visit'],
];
const MOVERS_SHOWN = 8;

const HUBS_SHOWN = 8;

/** Where cargo changes ship, baseline against scenario (each side's transshipment summary from POST /api/whatif). */
function TransshipShift({ base, scen, atBase }) {
  const b = base?.transshipment; const s = scen?.transshipment;
  if (!b || !s) return null;
  const by = (t) => new Map(t.hubs.map((h) => [h.port, h]));
  const B = by(b); const S = by(s);
  const rows = [...new Set([...B.keys(), ...S.keys()])].map((port) => {
    const x = B.get(port); const y = S.get(port);
    return { port, b: x?.teu || 0, s: y?.teu || 0, cb: x?.cost || 0, cs: y?.cost || 0, rate: (x || y).cost_per_teu };
  });
  const shown = (atBase ? rows.sort((p, q) => q.b - p.b) : rows.sort((p, q) => Math.abs(q.s - q.b) - Math.abs(p.s - p.b) || q.s - p.s)).slice(0, HUBS_SHOWN);
  const gained = rows.filter((r) => !r.b && r.s).map((r) => r.port);
  const lost = rows.filter((r) => r.b && !r.s).map((r) => r.port);
  const teu = (v) => fmtNum(Math.round(v));
  return (
    <InstrumentPanel title="Transshipment: where cargo changes ship" right={<span className="text-[12px] text-slate-400">baseline → scenario</span>}>
      <div className="wi-tsline">
        <span><b>{teu(b.teu)} → {teu(s.teu)}</b> TEU/wk transshipped ({sign(s.teu - b.teu, teu)})</span>
        <span><b>{fmtUsd(b.cost)} → {fmtUsd(s.cost)}</b> transshipment/wk ({sign(s.cost - b.cost)})</span>
        <span><b>{b.hubs.length} → {s.hubs.length}</b> transfer hubs{gained.length ? ` · new: ${gained.slice(0, 4).join(', ')}` : ''}{lost.length ? ` · no longer used: ${lost.slice(0, 4).join(', ')}` : ''}</span>
      </div>
      <div className="tf-scroll">
        <table className="viz-table wi-table">
          <thead><tr><th>Hub</th><th className="r">$ / TEU</th><th className="r">Baseline TEU</th><th className="r">Scenario TEU</th><th className="r">Change</th><th className="r">Cost change</th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.port}><td>{r.port} <span className="dz-pct">{getPortName(r.port)}</span></td><td className="r">{fmtUsd(r.rate)}</td><td className="r">{teu(r.b)}</td><td className="r">{teu(r.s)}</td><td className="r">{sign(r.s - r.b, teu)}</td><td className="r">{sign(r.cs - r.cb)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="viz-note">{atBase ? `Busiest ${shown.length} of ${b.hubs.length} hubs of the re-routed baseline.` : `The ${shown.length} hubs whose transferred TEU changes most.`} Cost = TEU changing ship × the hub's transshipment charge (dataset tariff), as the ledger prices it. Full view of the recorded plan: Network → Transshipment.</div>
    </InstrumentPanel>
  );
}

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

function Kpi({ k, base, scen, fmt = fmtUsd, deltaFmt, good = 'up', src = 'Engine re-evaluation', def }) {
  const d = scen != null && base != null ? scen - base : null;
  const tone = d == null || Math.abs(d) < 1e-9 ? '' : (d > 0) === (good === 'up') ? 'is-good' : 'is-bad';
  return (
    <div className="wi-kpi">
      <div className="k">{k}</div>
      <div className="v">{scen != null ? fmt(scen) : '—'}</div>
      <div className={`d ${tone}`}>{d == null ? '' : deltaFmt ? deltaFmt(d) : sign(d, fmt)} <span>vs {base != null ? fmt(base) : '—'}</span></div>
      <SourceChip src={src} def={def} />
    </div>
  );
}

const NO_CLOSURE = { preset: null, closed: [], ports: [] };

export default function WhatIf({ optimizationState = null }) {
  const [run, setRun] = useState(getSelectedRun());
  useEffect(() => subscribeRun(setRun), []);
  const [demandM, setDemandM] = useState(1);
  const [fuelM, setFuelM] = useState(1);
  const [closure, setClosure] = useState(NO_CLOSURE);
  const closureKey = JSON.stringify(closure);
  const [market, setMarket] = useState(NO_MARKET);
  const marketKey = JSON.stringify(market);
  // A new run starts with everything open. Only on a real change of run: an effect re-run on mount (React's dev
  // double-invoke) must not undo a closure a palette command has just set.
  const runSeen = useRef(runKey(run));
  useEffect(() => {
    const k = runKey(run);
    if (k === runSeen.current) return;
    runSeen.current = k;
    setClosure(NO_CLOSURE);
  }, [run]);
  // Command-palette scenarios (design D10: "close Suez", "fuel +20%"): change only the levers named.
  useScenarioIntent('whatif', ({ patch }) => {
    if (patch.fuelM != null) setFuelM(patch.fuelM);
    if (patch.demandM != null) setDemandM(patch.demandM);
    if ('closure' in patch) setClosure(patch.closure ? { preset: patch.closure, closed: [], ports: [] } : NO_CLOSURE);
    if (patch.market) setMarket((m) => ({ ...m, ...patch.market }));
  });
  const planServices = optimizationState?.global?.selected_services || [];
  const portOptions = useMemo(() => {
    const calls = new Map();
    planServices.forEach((sv) => [...new Set(sv.ports || [])].forEach((p) => calls.set(p, (calls.get(p) || 0) + 1)));
    return [...calls.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([code, n]) => ({ code, calls: n, name: getPortName(code) }));
  }, [planServices]);
  const [state, setState] = useState({ status: 'idle', data: null, error: null });
  const reqId = useRef(0);

  useEffect(() => {
    const id = ++reqId.current;
    setState((s) => ({ ...s, status: 'loading' }));
    const t = setTimeout(async () => {
      try {
        const r = await fetch('/api/whatif', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run, demand_multiplier: demandM, fuel_multiplier: fuelM,
            preset: closure.preset, closed_passages: closure.closed, closed_ports: closure.ports, ...marketPayload(market) }),
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
  }, [run, demandM, fuelM, closureKey, marketKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const data = state.data;
  const base = data?.baseline;
  const scen = data?.scenario;
  const movers = useMemo(() => {
    if (!base || !scen) return [];
    const b = new Map(base.per_service.map((s) => [s.id, s]));
    const sc = new Map(scen.per_service.map((s) => [s.id, s]));
    // A service suspended by a closure is absent from the scenario: it earns and costs nothing there.
    const ids = [...new Set([...b.keys(), ...sc.keys()])];
    return ids.map((id) => {
      const o = b.get(id) || { profit: 0, revenue: 0, leg_load_factor: null };
      const s = sc.get(id) || { profit: 0, leg_load_factor: null, suspended: true };
      return { id, base: o.profit, scen: s.profit, d: s.profit - o.profit, lfB: o.leg_load_factor, lfS: s.leg_load_factor, suspended: Boolean(s.suspended) };
    }).filter((m) => Math.abs(m.d) > 0.5).sort((x, y) => Math.abs(y.d) - Math.abs(x.d)).slice(0, MOVERS_SHOWN);
  }, [base, scen]);
  const maxMove = Math.max(1, ...movers.map((m) => Math.abs(m.d)));
  const lossBase = base ? base.per_service.filter((s) => s.profit < 0).length : 0;
  const lossScen = scen ? scen.per_service.filter((s) => s.profit < 0).length : 0;
  const atBase = demandM === 1 && fuelM === 1 && !closureActive(closure) && !marketActive(market);
  const report = data?.disruption || null;
  // The map's view of the closure: which legs sail a detour, which services are suspended.
  const mapDisruption = useMemo(() => (report ? {
    closed: report.closed_passages || [], detourAvoid: report.detour_avoid || [],
    rerouted: new Set((report.rerouted_legs || []).map((l) => `${l.from}|${l.to}`)),
    suspended: new Set((report.suspended_services || []).map((x) => String(x.id))),
  } : null), [report]);
  const applyCase = (target, id) => {
    if (target === 'ports') setClosure({ preset: null, closed: [], ports: [id] });
    else {
      const preset = (data?.presets && Object.entries(data.presets).find(([, v]) => v.closed.length === 1 && v.closed[0] === id)?.[0])
        || CLOSURE_PRESETS.find((p) => p.key === id)?.key || null;
      setClosure(preset ? { preset, closed: [], ports: [] } : { preset: null, closed: [id], ports: [] });
    }
    if (typeof window !== 'undefined') window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const busy = state.status === 'loading';

  return (
    <div className="cx-page-body space-y-3">
      <PageHead
        section="Scenarios"
        eyebrow="What-if"
        title="What-if: fuel, demand and closures"
        subtitle="Re-price the plan on screen without re-running the optimizer. Services, departures and vessel classes stay as planned; a closed strait or canal sends its legs on a detour (more vessels, more fuel); cargo is re-routed over what is left by the engine's flow LP and priced by its ledger."
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
          <button type="button" className="cmp-btn" disabled={atBase} onClick={() => { setDemandM(1); setFuelM(1); setClosure(NO_CLOSURE); setMarket(NO_MARKET); }}>Reset to plan</button>
        </div>
        <ClosureControls closure={closure} setClosure={setClosure} ports={portOptions} />
        <MarketControls market={market} setMarket={setMarket} info={data?.market} />
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
            <Kpi k="Weekly profit" base={base.profit} scen={scen.profit} def="revenue − cost, $/week" />
            <Kpi k="Margin" def="profit ÷ revenue" base={base.margin_pct} scen={scen.margin_pct} fmt={(v) => fmtPct(v)} deltaFmt={(d) => `${d >= 0 ? '+' : '−'}${Math.abs(d).toFixed(1)} pp`} />
            <Kpi k="Revenue" base={base.revenue} scen={scen.revenue} def={market.rateMode === 'wci_lanes' ? 'TEU × dataset rate × WCI lane ratio' : market.rateM !== 1 ? `TEU × dataset rate × ${market.rateM.toFixed(2)}` : 'TEU carried × dataset rate'} src={market.rateMode === 'wci_lanes' ? 'Engine + Drewry WCI' : undefined} />
            <Kpi k="Total cost" base={base.total_cost} scen={scen.total_cost} good="down" def="sum of the cost lines below" />
            <Kpi k="Coverage" def="TEU carried ÷ weekly demand" base={base.coverage_pct} scen={scen.coverage_pct} fmt={(v) => fmtPct(v)} deltaFmt={(d) => `${d >= 0 ? '+' : '−'}${Math.abs(d).toFixed(1)} pp`} />
            <Kpi k="TEU carried / wk" def="flow LP over the plan's services" base={base.served_teu} scen={scen.served_teu} fmt={fmtNum} deltaFmt={(d) => sign(d, fmtNum)} />
          </div>

          {report && (
            <div className="grid grid-cols-12 gap-3">
              <div className="col-span-12 xl:col-span-7 min-w-0">
                <InstrumentPanel title="Detours on the map" right={<span className="text-[12px] text-slate-400">orange = detour · dashed = suspended</span>} bodyPadding="flush">
                  <div style={{ height: 420 }}>
                    <WorldMap optimizationState={optimizationState} selectedServices={planServices} disruption={mapDisruption}
                      drawKey={`whatif|${closureKey}`} />
                  </div>
                </InstrumentPanel>
              </div>
              <div className="col-span-12 xl:col-span-5 min-w-0">
                <InstrumentPanel title="What the closure does">
                  <DisruptionReport report={report} scen={scen} base={base} />
                </InstrumentPanel>
              </div>
            </div>
          )}

          {(market.war || market.bunker === 'market') && (
            <div className="grid grid-cols-12 gap-3">
              {market.war && (
                <div className={`col-span-12 ${market.bunker === 'market' ? 'xl:col-span-7' : ''} min-w-0`}>
                  <InstrumentPanel title="War-risk premiums" right={<span className="text-[12px] text-slate-400">JWC listed areas · per departure</span>}>
                    <WarRiskReport war={data.market?.war_risk} />
                  </InstrumentPanel>
                </div>
              )}
              {market.bunker === 'market' && (
                <div className={`col-span-12 ${market.war ? 'xl:col-span-5' : ''} min-w-0`}>
                  <InstrumentPanel title="Bunker prices by port" right={<span className="text-[12px] text-slate-400">engine rule · VLSFO</span>}>
                    <BunkerReport bunker={data.market?.bunker} scen={scen} />
                  </InstrumentPanel>
                </div>
              )}
            </div>
          )}

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
                  <div className="text-[12px] text-slate-400 p-1">Move a slider, pick a preset or close a chokepoint to see which services gain or lose.</div>
                ) : (
                  <ul className="wi-movers">
                    {movers.map((m) => (
                      <li key={m.id} title={`${m.id}: ${fmtUsd(m.base)} → ${fmtUsd(m.scen)}; leg load factor ${m.lfB != null ? fmtPct(m.lfB * 100) : '—'} → ${m.lfS != null ? fmtPct(m.lfS * 100) : '—'}`}>
                        <span className="id">{m.id}{m.suspended ? ' · suspended' : ''}</span>
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

          <TransshipShift base={base} scen={scen} atBase={atBase} />

          <InstrumentPanel title="Freight index: today's spot against the dataset" right={<span className="text-[12px] text-slate-400">Drewry WCI · {data.market?.freight?.as_of}</span>}>
            <FreightLanes freight={data.market?.freight} market={market} onUse={(r) => setMarket({ ...market, rateMode: 'uniform', rateM: Math.min(3, Math.max(0.3, Math.round(r * 20) / 20)) })} />
          </InstrumentPanel>

          <div className="viz-note">
            Method: {data.model.method}. {data.model.services} services, {fmtNum(data.model.path_columns)} path columns (≤ {data.model.max_transfers} transfers), dataset {data.dataset?.label || data.dataset?.key || String(data.dataset)}.
            {' '}Fuel scales exactly (fuel cost = departures × tonnes × price). Demand changes re-route cargo inside fixed capacity, so revenue does not grow in proportion once legs are full. Nothing here re-runs the GA or the MILP.
          </div>
        </div>
      )}

      <ResilienceRanking run={run} onApply={applyCase} />

      <Provenance
        source="POST /api/whatif → src/network/flow LP + src/network/ledger.compute_ledger"
        sourceStatus={state.status === 'ok' ? 'available' : 'no_data'}
        attribution="Read-only re-evaluation of the recorded plan"
        license="Internal artifact"
      />
    </div>
  );
}
