/**
 * Emissions.jsx — CO2 and carbon cost of the plan on screen (2026-10-28, features #14-#18).
 *
 *   #14 CO2 per TEU and per TEU-km, and each service's CII rating (A-E)
 *   #15 EU ETS: CO2 covered (EU/EEA voyages and berths) priced at an EUA slider, EUR/USD from the ECB
 *   #16 ECA: the share of every leg inside a SOx emission control area burns marine gas oil (premium slider)
 *   #17 slow steaming: a speed slider within the deployed classes' LINERLIB speed range (cube-law fuel)
 *   #18 profit vs CO2 front over that speed range
 *
 * Numbers: POST /api/emissions and /api/emissions/front (backend/emissions.py) on the run selected in the header —
 * the recorded services, re-routed by the flow LP and priced by the ledger, with this page's fuel and carbon bill.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Provenance } from '../../components/console/p12.jsx';
import { SourceChip } from '../../components/common/Figure.jsx';
import WorldMap from '../../components/map/WorldMap.jsx';
import { getSelectedRun, subscribeRun, runLabel } from '../../services/runSelection.js';
import { setMapPrefs, useMapPrefs } from '../../services/mapPrefsStore.js';
import { fmtNum, fmtUsd } from '../../utils/formatters.js';

const DEBOUNCE_MS = 350;
const DEFAULTS = { speed: 1, eua: 75, ets: true, etsYear: 2026, eca: true, mgo: 200, ciiYear: 2026, dwt: 13 };
const GRADES = ['A', 'B', 'C', 'D', 'E'];
const t0 = (v) => fmtNum(Math.round(v));
const signedUsd = (v) => `${v > 0 ? '+' : v < 0 ? '−' : '±'}${fmtUsd(Math.abs(v))}`;
const pctChange = (a, b) => (b ? ((a - b) / Math.abs(b)) * 100 : null);

function body(run, s) {
  return { run, speed_factor: s.speed, eua_eur_per_t: s.eua, ets: s.ets, ets_year: s.etsYear, eca: s.eca,
    mgo_premium_usd_per_t: s.mgo, cii_year: s.ciiYear, dwt_per_teu: s.dwt };
}

async function post(url, payload) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const b = await r.json().catch(() => null);
  if (!r.ok || !b) {
    const e = new Error(b?.detail || `HTTP ${r.status}`);
    e.unavailable = !b || (r.status === 500 && !b?.detail);
    throw e;
  }
  return b;
}

export default function Emissions({ optimizationState = null }) {
  const [run, setRun] = useState(getSelectedRun());
  useEffect(() => subscribeRun(setRun), []);
  const [s, setS] = useState(DEFAULTS);
  const set = (patch) => setS((x) => ({ ...x, ...patch }));
  const [state, setState] = useState({ status: 'idle', data: null, error: null });
  const [front, setFront] = useState({ status: 'idle', data: null, error: null, key: null });
  const reqId = useRef(0);
  const settingsKey = JSON.stringify({ run, ...s, speed: undefined });
  useEffect(() => { set({ speed: 1 }); }, [run]);

  useEffect(() => {
    const id = ++reqId.current;
    setState((x) => ({ ...x, status: 'loading' }));
    const t = setTimeout(async () => {
      try {
        const d = await post('/api/emissions', body(run, s));
        if (id === reqId.current) setState({ status: 'ok', data: d, error: null });
      } catch (e) {
        if (id === reqId.current) setState({ status: e.unavailable ? 'unavailable' : 'error', data: null, error: String(e.message || e) });
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [run, s]);

  const computeFront = async () => {
    setFront({ status: 'loading', data: null, error: null, key: settingsKey });
    try {
      setFront({ status: 'ok', data: await post('/api/emissions/front', body(run, s)), error: null, key: settingsKey });
    } catch (e) {
      setFront({ status: 'error', data: null, error: String(e.message || e), key: settingsKey });
    }
  };

  const d = state.data;
  const plan = d?.plan;
  const sc = d?.scenario;
  const range = d?.settings?.speed_range;
  // whole-percent slider stops inside the range every deployed class can sail
  const sLo = range ? Math.ceil(range.min * 100 - 1e-6) / 100 : 0.85;
  const sHi = range ? Math.floor(range.max * 100 + 1e-6) / 100 : 1.05;
  const fx = d?.settings?.fx;
  const slow = Math.abs(s.speed - 1) > 1e-6;
  const mapPrefs = useMapPrefs();
  const showEca = () => setMapPrefs({ layers: { eca: true } });

  return (
    <div className="cx-page-body space-y-3">
      <PageHead
        section="Scenarios"
        eyebrow="Emissions"
        title="Emissions, carbon cost and slow steaming"
        subtitle="CO2 of the plan on screen, what the EU ETS and the sulphur rules in emission control areas cost it, and what sailing slower changes. Services and departures stay as planned; cargo is re-routed by the flow LP and priced by the ledger."
        pills={[
          { tone: 'selected', label: runLabel(run, d?.dataset) },
          { tone: state.status === 'ok' ? 'available' : state.status === 'loading' ? 'active' : 'no_data',
            label: state.status === 'ok' ? `${t0(sc.co2_t)} t CO2 / wk` : state.status === 'loading' ? 'computing…' : state.status === 'unavailable' ? 'needs backend' : state.status },
        ]}
      />

      <InstrumentPanel title="Assumptions" right={<span className="text-[12px] text-slate-400">applies to the run selected in the header</span>}>
        <div className="em-controls">
          <Slider id="em-speed" label="Sailing speed" value={s.speed} min={sLo} max={sHi} step={0.01}
            fmt={(v) => `${Math.round(v * 100)}% of design`} onChange={(v) => set({ speed: v })}
            hint={range ? `${Math.round(sLo * 100)}–${Math.round(sHi * 100)}%: the slowest / fastest every deployed class can sail (${range.min_binding_class} / ${range.max_binding_class}, LINERLIB min / max speed)` : null} />
          <Slider id="em-eua" label="EU allowance (EUA) price" value={s.eua} min={0} max={200} step={1}
            fmt={(v) => `€${v} / t CO2`} onChange={(v) => set({ eua: v })}
            hint={fx ? `× ${fx.rate.toFixed(4)} USD/EUR (${fx.source}${fx.date ? `, ${fx.date}` : ''})` : null} disabled={!s.ets} />
          <Slider id="em-mgo" label="Gas-oil premium in ECAs" value={s.mgo} min={0} max={600} step={10}
            fmt={(v) => `+$${v} / t`} onChange={(v) => set({ mgo: v })} disabled={!s.eca}
            hint="over the plan's bunker price: marine gas oil (0.10% S) minus the fuel the plan prices; set it to the market spread" />
          <Slider id="em-dwt" label="Deadweight per TEU (for CII)" value={s.dwt} min={10} max={16} step={0.5}
            fmt={(v) => `${v} t / TEU`} onChange={(v) => set({ dwt: v })}
            hint="LINERLIB gives no deadweight: DWT = capacity × this ratio (an assumption)" />
        </div>
        <div className="em-toggles" role="group" aria-label="Rules applied">
          <label className="em-check"><input type="checkbox" checked={s.ets} onChange={(e) => set({ ets: e.target.checked })} /> EU ETS</label>
          <label className="em-check">year
            <select value={s.etsYear} onChange={(e) => set({ etsYear: Number(e.target.value) })} disabled={!s.ets} aria-label="EU ETS year">
              <option value={2024}>2024 (40% surrendered)</option><option value={2025}>2025 (70%)</option><option value={2026}>2026+ (100%)</option>
            </select>
          </label>
          <label className="em-check"><input type="checkbox" checked={s.eca} onChange={(e) => set({ eca: e.target.checked })} /> ECA sulphur limit</label>
          <label className="em-check">CII year
            <select value={s.ciiYear} onChange={(e) => set({ ciiYear: Number(e.target.value) })} aria-label="CII year">
              {[2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030].map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </label>
          <button type="button" className="cmp-btn" onClick={() => setS(DEFAULTS)} disabled={JSON.stringify(s) === JSON.stringify(DEFAULTS)}>Reset</button>
        </div>
      </InstrumentPanel>

      {state.status === 'error' && <p className="dz-warn">Emissions failed: {state.error}</p>}
      {state.status === 'unavailable' && <p className="dz-warn">This page needs the backend (POST /api/emissions). {state.error}</p>}

      {sc && plan && (
        <>
          <div className="em-kpis">
            <Kpi label="CO2 per week" src="Engine fuel × IMO factor" def="t fuel × 3.114 (VLSFO) or 3.206 (MGO)" value={`${t0(sc.co2_t)} t`} delta={slow ? pctChange(sc.co2_t, plan.co2_t) : null} good="down" />
            <Kpi label="CO2 per TEU-km" src="Model" def="CO2 ÷ TEU-km carried" value={sc.g_co2_per_teu_km != null ? `${sc.g_co2_per_teu_km.toFixed(1)} g` : '—'} delta={slow ? pctChange(sc.g_co2_per_teu_km, plan.g_co2_per_teu_km) : null} good="down" />
            <Kpi label="CO2 per TEU carried" src="Model" def="CO2 ÷ TEU carried" value={sc.co2_per_teu_t != null ? `${sc.co2_per_teu_t.toFixed(2)} t` : '—'} />
            <Kpi label="EU ETS cost" src="EU ETS rules · ECB FX" def="covered CO2 × phase-in × EUA" value={`${fmtUsd(sc.ets_cost)}/wk`} sub={`${t0(sc.ets_co2_t)} t covered`} />
            <Kpi label="Gas oil in ECAs" src="MARPOL VI ECAs" def="MGO premium on ECA miles" value={`${fmtUsd(sc.mgo_extra_cost)}/wk`} sub={`${t0(sc.mgo_t)} t · ${(sc.eca_share_of_nm * 100).toFixed(0)}% of miles`} />
            <Kpi label="Profit after carbon & sulphur" src="Engine ledger − rules" def="profit − ETS − ECA fuel" value={`${fmtUsd(sc.profit)}/wk`} sub={slow ? `${signedUsd(sc.profit - plan.profit)} vs design speed` : `ledger before: ${fmtUsd(sc.ledger_profit)}`} />
            <Kpi label="Vessels" src="Engine ledger" def="vessels for weekly departures" value={fmtNum(sc.vessels)} sub={slow ? `${plan.vessels} at design speed` : null} />
          </div>
          {!sc.valid && (
            <p className="dz-warn" role="status">
              At this speed the plan breaks a ledger rule ({[...new Set((sc.violations || []).map((v) => v.type))].join(', ') || 'see the engine log'}):
              slower rotations need more vessels per weekly departure than the fleet has. Read profit as a lower bound.
            </p>
          )}
          {slow && sc.served_teu < plan.served_teu - 1 && (
            <p className="viz-note">At {Math.round(s.speed * 100)}% speed {t0(plan.served_teu - sc.served_teu)} TEU/wk no longer fit their transit-time limits and are not carried.</p>
          )}
          {d.suspended?.length > 0 && <p className="viz-note">Suspended at this speed: {d.suspended.map((x) => `${x.id} (${x.reason})`).join('; ')}.</p>}

          <div className="grid grid-cols-12 gap-3">
            <div className="col-span-12 xl:col-span-7 min-w-0">
              <InstrumentPanel title="Profit vs CO2 across sailing speeds"
                right={<button type="button" className="cmp-btn" onClick={computeFront} disabled={front.status === 'loading'}>
                  {front.status === 'loading' ? 'Computing…' : front.data && front.key === settingsKey ? 'Recompute' : 'Compute the front'}</button>}>
                {front.status === 'idle' && <p className="text-[12px] text-slate-400 max-w-[80ch]">Re-evaluates the plan at seven speeds from the slowest the fleet allows to design speed (about 10 s), with the carbon and sulphur settings above.</p>}
                {front.status === 'error' && <p className="dz-warn">Front failed: {front.error}</p>}
                {front.data && <FrontChart pts={front.data.points} current={s.speed} stale={front.key !== settingsKey} />}
              </InstrumentPanel>
            </div>
            <div className="col-span-12 xl:col-span-5 min-w-0">
              <InstrumentPanel title={`CII ratings ${s.ciiYear}`} right={<span className="text-[12px] text-slate-400">one vessel per service · reduction {d.settings.cii_reduction_pct}%</span>}>
                <GradeBar grades={sc.cii_grades} total={sc.services.length} />
                <p className="viz-note mt-2">
                  Attained AER = CO2 / (deadweight × miles) over a round voyage; required = 1984 × DWT^−0.489 × (1 − {d.settings.cii_reduction_pct}%);
                  {' '}A ≤ 0.83 · B ≤ 0.94 · C ≤ 1.07 · D ≤ 1.19 · E above (container ships, IMO MEPC.353/354(78)). Deadweight assumed {s.dwt} t per TEU.
                </p>
              </InstrumentPanel>
            </div>
          </div>

          <InstrumentPanel title="Services" right={<span className="text-[12px] text-slate-400">largest emitters first</span>} bodyPadding="flush">
            <div className="tf-scroll">
              <table className="viz-table wi-table tf-table em-table">
                <thead><tr><th>Service</th><th className="r">Speed</th><th className="r">CO2 t / wk</th><th className="r">g / TEU-km</th><th className="r">In ECAs</th><th className="r">ETS t / wk</th><th className="r">ETS + gas oil / wk</th><th>CII</th></tr></thead>
                <tbody>
                  {sc.services.map((r) => (
                    <tr key={r.id}>
                      <td>{r.id}<div className="dz-pct">{r.vessel_class} · {r.departures_per_week}× / wk</div></td>
                      <td className="r">{r.speed_knots.toFixed(1)} kn</td>
                      <td className="r">{t0(r.co2_t)}</td>
                      <td className="r">{r.g_co2_per_teu_km != null ? r.g_co2_per_teu_km.toFixed(0) : '—'}</td>
                      <td className="r">{(r.eca_share * 100).toFixed(0)}%</td>
                      <td className="r">{t0(r.ets_co2_t)}</td>
                      <td className="r">{fmtUsd(r.ets_usd + r.mgo_extra_usd)}</td>
                      <td><span className={`em-grade em-g${r.cii.rating}`} title={`attained ${r.cii.attained} / required ${r.cii.required} = ${r.cii.ratio}`}>{r.cii.rating}</span> <span className="dz-pct">{r.cii.ratio.toFixed(2)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </InstrumentPanel>

          <InstrumentPanel title="Emission control areas and the plan"
            right={!mapPrefs.layers.eca ? <button type="button" className="cmp-btn" onClick={showEca}>Show ECA zones</button> : <span className="text-[12px] text-slate-400">teal = 0.10% sulphur zone</span>} bodyPadding="flush">
            <div style={{ height: 420 }}>
              <WorldMap optimizationState={optimizationState} selectedServices={optimizationState?.global?.selected_services || []} dataset={d.dataset} drawKey="emissions" />
            </div>
          </InstrumentPanel>
        </>
      )}

      <Provenance
        source="POST /api/emissions → backend/emissions.py (engine service models + flow LP + ledger); ECA polygons Marine Regions (CC-BY 4.0); EUR/USD ECB"
        sourceStatus={state.status === 'ok' ? 'available' : 'no_data'}
        attribution="Read-only re-evaluation of the recorded plan; IMO MEPC.364(79) CO2 factors, MEPC.353/354(78) CII"
        license="Internal artifact"
      />
    </div>
  );
}

function Slider({ id, label, value, min, max, step, onChange, fmt, hint, disabled }) {
  return (
    <div className={`em-slider${disabled ? ' is-off' : ''}`}>
      <label htmlFor={id} className="dz-label">{label}</label>
      <div className="em-slider-row">
        <input id={id} type="range" min={min} max={max} step={step} value={Math.min(max, Math.max(min, value))} disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))} aria-valuetext={fmt(value)} />
        <output htmlFor={id}>{fmt(value)}</output>
      </div>
      {hint && <div className="dz-pct em-hint">{hint}</div>}
    </div>
  );
}

function Kpi({ label, value, sub, delta, good, src, def }) {
  const tone = delta == null || Math.abs(delta) < 0.05 ? '' : (delta < 0) === (good === 'down') ? 'em-up' : 'em-down';
  return (
    <div className="em-kpi">
      <span>{label}</span>
      <b>{value}</b>
      {delta != null && <i className={tone}>{delta > 0 ? '+' : delta < 0 ? '−' : '±'}{Math.abs(delta).toFixed(1)}% vs design speed</i>}
      {sub && <i>{sub}</i>}
      <SourceChip src={src} def={def} />
    </div>
  );
}

function GradeBar({ grades, total }) {
  return (
    <div>
      <div className="em-gradebar" role="img" aria-label={GRADES.map((g) => `${g}: ${grades[g] || 0}`).join(', ')}>
        {GRADES.map((g) => (grades[g] ? <span key={g} className={`em-g${g}`} style={{ flexGrow: grades[g] }} title={`${g}: ${grades[g]} services`}>{g} {grades[g]}</span> : null))}
      </div>
      <div className="em-gradelegend">{GRADES.map((g) => <span key={g}><span className={`em-grade em-g${g}`}>{g}</span> {grades[g] || 0}</span>)} <span className="dz-pct">of {total} services</span></div>
    </div>
  );
}

/** One series: weekly profit (y) against weekly CO2 (x), one dot per speed, joined in speed order. */
function FrontChart({ pts, current, stale }) {
  const [hover, setHover] = useState(null);
  const W = 640; const H = 300; const M = { l: 64, r: 16, t: 14, b: 40 };
  const xs = pts.map((p) => p.co2_t); const ys = pts.map((p) => p.profit);
  const pad = (lo, hi) => { const d = (hi - lo) || Math.abs(hi) || 1; return [lo - d * 0.08, hi + d * 0.08]; };
  const [x0, x1] = pad(Math.min(...xs), Math.max(...xs));
  const [y0, y1] = pad(Math.min(0, ...ys), Math.max(...ys));
  const X = (v) => M.l + ((v - x0) / (x1 - x0)) * (W - M.l - M.r);
  const Y = (v) => H - M.b - ((v - y0) / (y1 - y0)) * (H - M.t - M.b);
  const yt = useMemo(() => Array.from({ length: 5 }, (_, i) => y0 + ((y1 - y0) * i) / 4), [y0, y1]);
  const xt = useMemo(() => Array.from({ length: 5 }, (_, i) => x0 + ((x1 - x0) * i) / 4), [x0, x1]);
  const sorted = [...pts].sort((a, b) => a.speed_factor - b.speed_factor);
  const cur = pts.reduce((b, p) => (Math.abs(p.speed_factor - current) < Math.abs(b.speed_factor - current) ? p : b), pts[0]);
  const h = hover != null ? sorted[hover] : null;
  return (
    <div className="em-front">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Weekly profit against weekly CO2, one point per sailing speed">
        {yt.map((v, i) => <g key={`y${i}`}><line x1={M.l} x2={W - M.r} y1={Y(v)} y2={Y(v)} stroke="var(--viz-grid)" /><text x={M.l - 6} y={Y(v) + 4} textAnchor="end" className="em-ax">{fmtUsd(v)}</text></g>)}
        {xt.map((v, i) => <text key={`x${i}`} x={X(v)} y={H - M.b + 16} textAnchor="middle" className="em-ax">{t0(v)}</text>)}
        {y0 < 0 && <line x1={M.l} x2={W - M.r} y1={Y(0)} y2={Y(0)} stroke="var(--viz-base)" />}
        <text x={(M.l + W - M.r) / 2} y={H - 6} textAnchor="middle" className="em-ax">t CO2 per week</text>
        <polyline fill="none" stroke="var(--viz-1)" strokeWidth="2" points={sorted.map((p) => `${X(p.co2_t)},${Y(p.profit)}`).join(' ')} />
        {sorted.map((p, i) => (
          <g key={p.speed_factor} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)} tabIndex={0}>
            <circle cx={X(p.co2_t)} cy={Y(p.profit)} r="14" fill="transparent" />
            <circle cx={X(p.co2_t)} cy={Y(p.profit)} r={p === cur ? 6 : 4.5} fill={p.valid ? 'var(--viz-1)' : 'var(--cx-bg-2, #050d18)'}
              stroke={p === cur ? 'var(--viz-ink)' : 'var(--viz-1)'} strokeWidth="2" />
            {(i === 0 || i === sorted.length - 1 || p === cur) && (
              <text x={X(p.co2_t)} y={Y(p.profit) - 11} textAnchor="middle" className="em-lbl">{Math.round(p.speed_factor * 100)}%</text>
            )}
          </g>
        ))}
      </svg>
      {h && (
        <div className="em-tip" style={{ left: `${(X(h.co2_t) / W) * 100}%`, top: `${(Y(h.profit) / H) * 100}%` }} role="status">
          <b>{Math.round(h.speed_factor * 100)}% of design speed</b>
          <div>Profit {fmtUsd(h.profit)}/wk · CO2 {t0(h.co2_t)} t/wk</div>
          <div>{t0(h.served_teu)} TEU/wk carried · {h.vessels} vessels{h.valid ? '' : ' · breaks the fleet rule'}</div>
          <div>{h.g_co2_per_teu_km?.toFixed(1)} g CO2/TEU-km · ETS {fmtUsd(h.ets_cost)}/wk</div>
          {!h.efficient && <div>Dominated: another speed earns more for less CO2</div>}
        </div>
      )}
      <div className="viz-note">
        Filled dot = the plan fits the fleet; hollow = it would need more vessels than the fleet has. Ringed = the speed set above.
        {' '}{pts.every((p) => p.efficient) ? 'Every speed is on the front: less CO2 always costs profit here.' : `${pts.filter((p) => !p.efficient).length} speed(s) are dominated (another earns more for less CO2).`}
        {stale && ' Settings changed since this front was computed: recompute.'}
      </div>
    </div>
  );
}
