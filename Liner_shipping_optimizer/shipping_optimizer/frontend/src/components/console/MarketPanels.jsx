/**
 * MarketPanels.jsx — market inputs of the What-if (2026-10-29, batch 6), see backend/market.py and backend/war_risk.py.
 *
 * #20 Freight rate: a uniform level (× the dataset's revenue per TEU), or the Drewry WCI lanes (each lane's spot
 *     rate ÷ the dataset's revenue on the same port pair, applied to every OD of that trade; other ODs take the slider).
 * #21 Bunker price: the dataset's uniform price, or Ship & Bunker's public VLSFO prices by port through the engine's
 *     own rule (cheapest observed port on the rotation, else the Global 20 average).
 * #19 War risk: an additional premium per visit to a JWC listed area (JWLA-035), % of hull value, editable rates.
 */

import React from 'react';
import { fmtNum, fmtUsd } from '../../utils/formatters.js';
import { getPortName } from '../../utils/portLookup.js';

export const NO_MARKET = { rateMode: 'uniform', rateM: 1, bunker: 'dataset', war: false, warRates: {}, hull: 15000 };

export function marketActive(m) {
  return m.rateMode !== 'uniform' || m.rateM !== 1 || m.bunker !== 'dataset' || m.war;
}

export function marketPayload(m) {
  return {
    rate_mode: m.rateMode, rate_multiplier: m.rateM, bunker_mode: m.bunker,
    war_risk: m.war, war_rates_pct: m.warRates, hull_usd_per_teu: m.hull,
  };
}

const ZONE_LABEL = {
  gulf_hormuz: 'Persian Gulf, Hormuz, Gulf of Oman', red_sea_central: 'Red Sea 15.5–25.5° N',
  bab_al_mandab: 'Bab al-Mandab, Gulf of Aden, Indian Ocean', black_sea: 'Black Sea, Sea of Azov',
  gulf_of_guinea: 'Gulf of Guinea', cabo_delgado: 'Cabo Delgado', named_call: 'Call in a listed country',
};
const pct = (v) => `${Number(v).toFixed(v < 1 ? 2 : 1)}%`;
const x2 = (v) => (v == null ? '—' : `${v.toFixed(2)}×`);
const usd = (v) => (v == null ? '—' : `$${fmtNum(Math.round(v))}`); // exact: index values are not abbreviated

function Toggle({ options, value, onChange, label }) {
  return (
    <div className="mk-toggle" role="group" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={v} type="button" className="cmp-btn" aria-pressed={value === v} onClick={() => onChange(v)}>{text}</button>
      ))}
    </div>
  );
}

export function MarketControls({ market, setMarket, info }) {
  const set = (patch) => setMarket({ ...market, ...patch });
  const freight = info?.freight;
  const defs = info?.war_risk?.definitions;
  return (
    <div className="mk-controls">
      <fieldset className="mk-field">
        <legend>Freight rate <span>#20</span></legend>
        <Toggle label="Freight rate mode" value={market.rateMode} onChange={(v) => set({ rateMode: v })}
          options={[['uniform', 'Uniform level'], ['wci_lanes', 'WCI lanes']]} />
        <div className="wi-slider">
          <div className="wi-slider-head">
            <label htmlFor="mk-rate">{market.rateMode === 'wci_lanes' ? 'Lanes without a WCI rate' : 'Rate level'}</label>
            <output htmlFor="mk-rate">{market.rateM.toFixed(2)}× <span>dataset revenue / TEU</span></output>
          </div>
          <input id="mk-rate" type="range" min={0.3} max={3} step={0.05} value={market.rateM} onChange={(e) => set({ rateM: Number(e.target.value) })} />
          <div className="wi-slider-scale"><span>0.30×</span><span>{freight ? `WCI composite ${usd(freight.composite.usd_per_feu)}/FEU · ${freight.as_of}` : 'Drewry WCI'}</span><span>3.00×</span></div>
        </div>
      </fieldset>

      <fieldset className="mk-field">
        <legend>Bunker price <span>#21</span></legend>
        <Toggle label="Bunker price source" value={market.bunker} onChange={(v) => set({ bunker: v })}
          options={[['dataset', 'Dataset (uniform)'], ['market', 'Market by port']]} />
        <p className="mk-hint">
          {market.bunker === 'market'
            ? 'Ship & Bunker public VLSFO prices. Each service buys at the cheapest priced port on its rotation, else the Global 20 average. The fuel slider still multiplies.'
            : 'The dataset assumption: one price for every service (LINERLIB, 600 USD/t).'}
        </p>
      </fieldset>

      <fieldset className="mk-field">
        <legend>War risk <span>#19</span></legend>
        <Toggle label="War-risk premiums" value={market.war ? 'on' : 'off'} onChange={(v) => set({ war: v === 'on' })}
          options={[['off', 'Off'], ['on', 'Add premiums']]} />
        {market.war && (
          <>
            <label className="mk-num">
              <span>Hull value</span>
              <input type="number" min={1000} max={60000} step={500} value={market.hull}
                onChange={(e) => set({ hull: Math.min(60000, Math.max(1000, Number(e.target.value) || 15000)) })} />
              <span>USD / TEU of capacity</span>
            </label>
            {defs && (
              <details className="mk-rates">
                <summary>Premium rates (% of hull value per 7-day visit)</summary>
                <div className="mk-rate-grid">
                  {[...defs.zones, { id: 'named_call', label: ZONE_LABEL.named_call, default_pct: defs.named_call.default_pct, source: defs.named_call.source }].map((z) => (
                    <label key={z.id} title={z.source}>
                      <span>{z.label}</span>
                      <input type="number" min={0} max={50} step={0.05}
                        value={market.warRates[z.id] ?? z.default_pct}
                        onChange={(e) => set({ warRates: { ...market.warRates, [z.id]: Number(e.target.value) } })} />
                    </label>
                  ))}
                </div>
                <p className="mk-hint">Defaults: published market levels, source on hover. Listed areas: JWC {defs.circular.id} ({defs.circular.date}).</p>
              </details>
            )}
          </>
        )}
      </fieldset>
    </div>
  );
}

export function FreightLanes({ freight, market, onUse }) {
  if (!freight) return null;
  const applied = freight.lanes_applied || {};
  return (
    <>
      <table className="viz-table wi-table mk-table">
        <thead>
          <tr><th>WCI lane</th><th className="r">Spot / FEU</th><th className="r">Spot / TEU</th><th className="r">Dataset / TEU</th><th className="r">Spot ÷ dataset</th>{market.rateMode === 'wci_lanes' && <th className="r">ODs moved</th>}<th /></tr>
        </thead>
        <tbody>
          {freight.lanes.map((l) => (
            <tr key={l.id}>
              <td>{l.label}{l.benchmark_note ? <span className="mk-note" title={l.benchmark_note}> *</span> : null}</td>
              <td className="r">{usd(l.usd_per_feu)}{l.change_wow_pct != null && <span className="mk-dim"> {l.change_wow_pct >= 0 ? '+' : ''}{l.change_wow_pct}%</span>}</td>
              <td className="r">{usd(l.usd_per_teu)}</td>
              <td className="r" title={l.benchmark_od ? `${l.benchmark_od[0]} → ${l.benchmark_od[1]}` : ''}>{usd(l.dataset_usd_per_teu)}</td>
              <td className="r"><b>{x2(l.ratio)}</b></td>
              {market.rateMode === 'wci_lanes' && <td className="r">{applied[l.id] ? `${applied[l.id].ods} · ${fmtNum(applied[l.id].teu)} TEU` : '—'}</td>}
              <td className="r">{l.ratio != null && <button type="button" className="cmp-btn mk-use" onClick={() => onUse(l.ratio)} title="Set the uniform rate level to this lane's ratio">Use</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="viz-note">
        Drewry World Container Index, {freight.as_of}: composite {usd(freight.composite.usd_per_feu)}/FEU; lanes from {freight.lane_source}. {freight.per_teu_rule}.
        {' '}Dataset / TEU is the LINERLIB revenue on the same port pair (* = stand-in port, hover). Spot rates are not realised average rates: the ratio says how today's spot market compares with the dataset, not what a carrier earns.
      </div>
    </>
  );
}

export function BunkerReport({ bunker, scen }) {
  if (!bunker || bunker.mode !== 'market') return null;
  const res = scen?.fuel_resolution || {};
  const groups = new Map();
  Object.values(res).forEach((r) => {
    const k = r.port || 'GLOBAL';
    const g = groups.get(k) || { port: r.port, price: r.price, n: 0 };
    g.n += 1;
    groups.set(k, g);
  });
  const rows = [...groups.values()].sort((a, b) => b.n - a.n);
  return (
    <>
      <table className="viz-table wi-table mk-table">
        <thead><tr><th>Bunkering port</th><th className="r">VLSFO USD/t</th><th className="r">Services</th></tr></thead>
        <tbody>
          {rows.map((g) => (
            <tr key={g.port || 'GLOBAL'}>
              <td>{g.port ? `${g.port} ${getPortName(g.port)}` : 'No priced port on rotation → Global 20 average'}</td>
              <td className="r">{fmtNum(g.price)}</td>
              <td className="r">{g.n}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="viz-note">
        Ship & Bunker public prices {bunker.as_of} ({bunker.age_days} d old{bunker.stale ? ', STALE' : ''}; {bunker.ports.length} port codes incl. aliases; G20 reference {fmtNum(bunker.reference.price)} USD/t).
        {bunker.dropped_stale?.length ? ` Left out as older than 14 days: ${bunker.dropped_stale.map((d) => d.hub).join(', ')}.` : ''}
        {' '}{bunker.rule}. Ports behind Ship & Bunker's subscription are not read.
      </div>
    </>
  );
}

export function WarRiskReport({ war }) {
  if (!war?.enabled) return null;
  const top = (war.services || []).slice(0, 8);
  return (
    <>
      <table className="viz-table wi-table mk-table">
        <thead><tr><th>Rate zone</th><th className="r">Rate</th><th className="r">Visits / wk</th><th className="r">Weekly premium</th><th className="r">Services</th></tr></thead>
        <tbody>
          {(war.zones || []).map((z) => (
            <tr key={z.zone}>
              <td>{ZONE_LABEL[z.zone] || z.zone}</td>
              <td className="r">{pct(war.rates_pct[z.zone])}</td>
              <td className="r">{fmtNum(z.visits_per_week)}</td>
              <td className="r">{fmtUsd(z.weekly)}</td>
              <td className="r">{z.services.length}</td>
            </tr>
          ))}
          <tr className="is-total"><td>Total</td><td /><td /><td className="r">{fmtUsd(war.weekly_total)}</td><td className="r">{(war.services || []).length}</td></tr>
        </tbody>
      </table>
      {top.length > 0 && (
        <ul className="mk-services">
          {top.map((s) => (
            <li key={s.id}>
              <span className="id">{s.id}</span>
              <span className="mk-dim">{s.vessel_class} · hull {fmtUsd(s.hull_value_usd)} · {s.frequency_per_week}/wk · {s.visits.map((v) => (v.port ? `${v.port} call` : ZONE_LABEL[v.rate_zone])).join(' + ')}</span>
              <span className="val">{fmtUsd(s.weekly)}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="viz-note">
        One premium per visit to a listed area (consecutive legs inside count once) at the highest rate of the zones touched, per departure; hull value {fmtUsd(war.hull_usd_per_teu)} per TEU of capacity (assumption).
        {' '}Areas: Joint War Committee {war.definitions.circular.id}, {war.definitions.circular.date}. Not modelled: visits over 7 days, crew war bonus, cargo war cover.
      </div>
    </>
  );
}
