/**
 * SeaConditions.jsx — forecast sea state and ocean currents along the plan's lanes (2026-10-29, features #12, #13).
 *
 *   #12 sea-state risk: the worst wave height forecast anywhere along each leg in the next days, by WMO sea-state code
 *   #13 currents in sail time: each leg's sail time at the service's speed with the forecast mean current along the
 *       lane, the rotation it adds or saves, and the vessels the ledger's rule N = ceil(T x f / 7) then needs
 *
 * Numbers: POST /api/weather/legs (backend/weather.py, Open-Meteo Marine) on the run selected in the header. The map's
 * Weather layers draw the same forecast points (services/seaState.js).
 */
import React, { useEffect, useMemo, useState } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Provenance } from '../../components/console/p12.jsx';
import { SourceChip } from '../../components/common/Figure.jsx';
import WorldMap from '../../components/map/WorldMap.jsx';
import { getSelectedRun, subscribeRun, runLabel } from '../../services/runSelection.js';
import { setMapPrefs, useMapPrefs } from '../../services/mapPrefsStore.js';
import { useSeaState, SEA_RISKS, seaRiskTone } from '../../services/seaState.js';
import { fmtNum } from '../../utils/formatters.js';

const RISK_LABEL = { low: 'Low', moderate: 'Moderate', high: 'High', severe: 'Severe' };
const hrs = (h) => `${h > 0 ? '+' : h < 0 ? '−' : '±'}${Math.abs(h).toFixed(1)} h`;
const when = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)} ${iso.slice(11, 16)}` : '—');

function RiskChip({ risk, hs }) {
  if (!risk) return <span className="dz-pct">—</span>;
  return (
    <span className="ws-risk">
      <span className="ws-dot" style={{ background: seaRiskTone(risk) }} aria-hidden="true" />
      {RISK_LABEL[risk]}{hs != null ? ` · ${hs.toFixed(1)} m` : ''}
    </span>
  );
}

export default function SeaConditions({ optimizationState = null }) {
  const [run, setRun] = useState(getSelectedRun());
  useEffect(() => subscribeRun(setRun), []);
  const [days, setDays] = useState(7);
  const st = useSeaState(run, days);
  const d = st.data;
  const [legView, setLegView] = useState('worst');
  const mapPrefs = useMapPrefs();

  const counts = d?.risk_counts || {};
  const nLegs = d?.legs?.length || 0;
  const worst = d?.legs?.[0];
  const t = d?.totals;
  const cycleChanged = useMemo(() => (d?.services || []).filter((s) => s.cycle_days_current !== s.cycle_days_plan), [d]);
  const vesselChanged = (d?.services || []).filter((s) => s.vessels_current !== s.vessels_plan);
  const legs = useMemo(() => {
    const L = [...(d?.legs || [])];
    if (legView === 'current') L.sort((a, b) => Math.abs(b.mean_along_current_kn || 0) - Math.abs(a.mean_along_current_kn || 0));
    return L.slice(0, 25);
  }, [d, legView]);
  const showLayers = () => setMapPrefs({ layers: { seastate: true, currents: true } });

  return (
    <div className="cx-page-body space-y-3">
      <PageHead
        section="Network"
        eyebrow="Sea state & currents"
        title="Weather and currents along the plan's lanes"
        subtitle="The forecast sea each leg's lane will see in the next days, and what the forecast currents do to the services' sail times and rotations. A forecast along the lanes over the window, not a voyage simulation: the pro-forma schedule does not say which day a ship passes where."
        pills={[
          { tone: 'selected', label: runLabel(run, d?.dataset) },
          { tone: st.status === 'ok' ? 'available' : st.status === 'loading' ? 'active' : 'no_data',
            label: st.status === 'ok' ? `forecast ${d.fetched_on}` : st.status === 'loading' ? 'fetching forecast…' : st.status === 'unavailable' ? 'needs backend' : st.status },
        ]}
      />

      <InstrumentPanel title="Forecast window" right={<span className="text-[12px] text-slate-400">Open-Meteo Marine · refreshed every 3 h</span>}>
        <div className="ws-controls" role="group" aria-label="Forecast days">
          {[3, 5, 7, 8].map((n) => (
            <button key={n} type="button" className="cmp-btn" aria-pressed={days === n} onClick={() => setDays(n)}>{n} days</button>
          ))}
          <span className="dz-pct">Sample point every {d?.settings?.sample_nm ?? 250} nm along each lane{d ? ` · ${fmtNum(d.points.length)} points` : ''}</span>
        </div>
      </InstrumentPanel>

      {st.status === 'loading' && <p className="text-[12px] text-slate-400">Fetching the forecast for every lane sample point: about a minute the first time for a run, cached for 3 hours after.</p>}
      {st.status === 'unavailable' && <p className="dz-warn">Needs the backend (POST /api/weather/legs). {st.error}</p>}
      {st.status === 'error' && <p className="dz-warn">Forecast failed: {st.error}</p>}

      {st.status === 'ok' && d && (
        <>
          <div className="em-kpis">
            <div className="em-kpi"><span>Worst sea on a lane</span><b>{worst?.hs_max_m != null ? `${worst.hs_max_m.toFixed(1)} m` : '—'}</b><i>{worst ? `${worst.from}→${worst.to} · ${worst.name} · ${when(worst.hs_max_at)} UTC` : ''}</i><SourceChip src="Open-Meteo Marine" def="max significant wave height, 7-day forecast" /></div>
            <div className="em-kpi"><span>Legs at high or severe risk</span><b>{(counts.high || 0) + (counts.severe || 0)} of {nLegs}</b><i>worst forecast wave height ≥ 4 m</i><SourceChip src="Open-Meteo · WMO 3700" def="sea state 6+ on any lane point" /></div>
            <div className="em-kpi"><span>Sea days per week with currents</span><b>{hrs((t.sea_days_current - t.sea_days_plan) * 24)}</b><i>{fmtNum(Math.round(t.sea_days_plan))} d planned · {((t.sea_days_current / t.sea_days_plan - 1) * 100).toFixed(2)}%</i><SourceChip src="Open-Meteo currents" def="Δ sea time, current along the lane" /></div>
            <div className="em-kpi"><span>Services whose cycle changes a day</span><b>{cycleChanged.length}</b><i>{cycleChanged.length ? cycleChanged.map((s) => `${s.id} ${s.cycle_days_plan}→${s.cycle_days_current} d`).slice(0, 3).join(' · ') : 'none'}</i><SourceChip src="Engine ledger rule" def="round trip rounded to whole days" /></div>
            <div className="em-kpi"><span>Vessels needed with currents</span><b>{t.vessels_current}</b><i>{t.vessels_current === t.vessels_plan ? `same as planned (${t.vessels_plan})` : `${t.vessels_plan} planned · ${vesselChanged.map((s) => s.id).join(', ')}`}</i><SourceChip src="Engine ledger rule" def="⌈cycle days × frequency ÷ 7⌉" /></div>
          </div>

          <InstrumentPanel title="Legs by forecast sea state" right={<span className="text-[12px] text-slate-400">WMO sea-state code of the worst wave height on the lane</span>}>
            <div className="em-gradebar ws-bar" role="img" aria-label={SEA_RISKS.map(([k]) => `${RISK_LABEL[k]}: ${counts[k] || 0}`).join(', ')}>
              {SEA_RISKS.map(([k, , tone]) => (counts[k] ? <span key={k} style={{ flexGrow: counts[k], background: tone, color: k === 'low' ? '#f8fafc' : '#0b1220' }} title={`${RISK_LABEL[k]}: ${counts[k]} legs`}>{counts[k]}</span> : null))}
            </div>
            <div className="em-gradelegend">
              {SEA_RISKS.map(([k, label, tone]) => <span key={k}><span className="ws-dot" style={{ background: tone }} aria-hidden="true" /> {label} · {counts[k] || 0}</span>)}
              <span className="dz-pct">of {nLegs} legs</span>
            </div>
          </InstrumentPanel>

          <InstrumentPanel title="Services" right={<span className="text-[12px] text-slate-400">largest change in sail time first</span>} bodyPadding="flush">
            <div className="tf-scroll">
              <table className="viz-table wi-table tf-table ws-table">
                <thead><tr><th>Service</th><th>Worst sea on its legs</th><th className="r">Sea days / rotation</th><th className="r">With currents</th><th className="r">Cycle (days)</th><th className="r">Vessels</th></tr></thead>
                <tbody>
                  {d.services.map((s) => (
                    <tr key={s.id}>
                      <td>{s.id}<div className="dz-pct">{s.vessel_class} · {s.speed_knots.toFixed(1)} kn · {s.departures_per_week}× / wk</div></td>
                      <td><RiskChip risk={s.risk} hs={s.hs_max_m} />{s.worst_leg && <div className="dz-pct">{s.worst_leg}</div>}</td>
                      <td className="r">{s.sea_days_plan.toFixed(1)}</td>
                      <td className="r">{hrs(s.delta_hours)}<div className="dz-pct">{s.delta_pct > 0 ? '+' : s.delta_pct < 0 ? '−' : '±'}{Math.abs(s.delta_pct).toFixed(2)}%</div></td>
                      <td className={`r${s.cycle_days_current !== s.cycle_days_plan ? ' ws-chg' : ''}`}>{s.cycle_days_plan}{s.cycle_days_current !== s.cycle_days_plan ? ` → ${s.cycle_days_current}` : ''}</td>
                      <td className={`r${s.vessels_current !== s.vessels_plan ? ' ws-chg' : ''}`}>{s.vessels_plan}{s.vessels_current !== s.vessels_plan ? ` → ${s.vessels_current}` : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </InstrumentPanel>

          <InstrumentPanel title="Legs"
            right={(
              <div className="rl-tabs" role="tablist" aria-label="Sort legs">
                {[['worst', 'Roughest sea'], ['current', 'Strongest current']].map(([k, label]) => (
                  <button key={k} type="button" role="tab" aria-selected={legView === k} aria-pressed={legView === k} className="cmp-btn" onClick={() => setLegView(k)}>{label}</button>
                ))}
              </div>
            )} bodyPadding="flush">
            <div className="tf-scroll">
              <table className="viz-table wi-table tf-table ws-table">
                <thead><tr><th>Leg</th><th>Sea-state risk</th><th>Worst at</th><th className="r">Hours ≥ 4 m there</th><th className="r">Mean current along the lane</th><th className="r">Lane</th></tr></thead>
                <tbody>
                  {legs.map((l) => (
                    <tr key={`${l.from}-${l.to}`}>
                      <td>{l.from} → {l.to}<div className="dz-pct">{l.services.join(', ')}</div></td>
                      <td><RiskChip risk={l.risk} hs={l.hs_max_m} />{l.name && <div className="dz-pct">{l.name} (WMO {l.code})</div>}</td>
                      <td>{l.worst_point ? `${l.worst_point[1].toFixed(1)}°, ${l.worst_point[0].toFixed(1)}°` : '—'}<div className="dz-pct">{when(l.hs_max_at)} UTC</div></td>
                      <td className="r">{l.hrs_ge4_at_worst ?? '—'}</td>
                      <td className="r">{l.mean_along_current_kn == null ? '—' : `${l.mean_along_current_kn > 0 ? '+' : l.mean_along_current_kn < 0 ? '−' : '±'}${Math.abs(l.mean_along_current_kn).toFixed(2)} kn`}<div className="dz-pct">{l.mean_along_current_kn > 0.05 ? 'with the ship' : l.mean_along_current_kn < -0.05 ? 'against the ship' : 'about neutral'}</div></td>
                      <td className="r">{fmtNum(Math.round(l.nm))} nm<div className="dz-pct">{l.lane === 'searoute' ? 'sea lane' : 'great circle'} · {l.samples} pts</div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="viz-note px-3 pb-3">Top 25 of {nLegs} legs. A leg's current is the mean forecast current projected on the direction of travel, averaged over its sample points.</p>
          </InstrumentPanel>

          <InstrumentPanel title="On the map"
            right={!(mapPrefs.layers.seastate && mapPrefs.layers.currents) ? <button type="button" className="cmp-btn" onClick={showLayers}>Show sea state and currents</button> : <span className="text-[12px] text-slate-400">Weather layers on · toggle them in Layers</span>} bodyPadding="flush">
            <div style={{ height: 440 }}>
              <WorldMap optimizationState={optimizationState} selectedServices={optimizationState?.global?.selected_services || []} dataset={d.dataset} drawKey="seaconditions" />
            </div>
          </InstrumentPanel>

          <InstrumentPanel title="Method">
            <ul className="viz-note ws-method">
              <li>Each leg is laid on its sea lane (searoute; great circle where no lane) and cut into pieces of at most {d.settings.sample_nm} nm; each piece's midpoint is a forecast point (points within {d.settings.grid_deg}° share one).</li>
              <li>Sea state: the highest hourly significant wave height forecast at any of the leg's points in the window, named by the WMO sea-state code (table 3700): up to 2.5 m low, 2.5–4 m moderate, 4–6 m high, above 6 m severe.</li>
              <li>Currents: the hourly forecast surface current (MeteoFrance SMOC, 0.08°) is averaged over the window and projected on each piece's course. Sail time = Σ distance / (service speed + current), never below half the speed; the ratio to still water scales the plan's own leg sail days.</li>
              <li>The cycle is re-declared in whole days and vessels follow the ledger's rule N = ⌈cycle × departures / 7⌉. Fuel and costs are not re-priced here.</li>
            </ul>
          </InstrumentPanel>
        </>
      )}

      <Provenance
        source="POST /api/weather/legs → backend/weather.py; Open-Meteo Marine API (wave model blend; currents MeteoFrance SMOC / Copernicus Marine)"
        sourceStatus={st.status === 'ok' ? 'available' : 'no_data'}
        attribution="Weather data by Open-Meteo.com (CC BY 4.0); currents from Copernicus Marine Service / Mercator Ocean SMOC"
        license="CC BY 4.0 (forecast data); free tier is non-commercial"
      />
    </div>
  );
}
