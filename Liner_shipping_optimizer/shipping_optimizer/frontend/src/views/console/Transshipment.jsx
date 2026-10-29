/**
 * Transshipment.jsx — where the plan's cargo changes ship (2026-10-29): the transfer hubs, what each costs a week,
 * which services hand cargo to which there, and the origin–destination lanes that ride more than one service.
 *
 * Numbers: utils/transshipment.js on the routed flows of the plan's own ledger (network_ledger.plan.flows) and the
 * dataset's port tariffs; the hub costs add up to the ledger's weekly transshipment cost, shown as a check.
 * Transit days and the feeder / hub-and-spoke split are the engine's own (strategy_report.extended_metrics).
 */
import React, { useMemo, useState } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Provenance } from '../../components/console/p12.jsx';
import { SourceChip } from '../../components/common/Figure.jsx';
import WorldMap from '../../components/map/WorldMap.jsx';
import { useTransshipment } from '../../services/transshipmentData.js';
import { setMapPrefs, useMapPrefs } from '../../services/mapPrefsStore.js';
import { downloadCsv } from '../../utils/exportData.js';
import { fmtNum, fmtUsd } from '../../utils/formatters.js';
import { getPortName } from '../../utils/portLookup.js';

const HUBS_SHOWN = 20;
const LANES_SHOWN = 25;
const pct = (v, d = 1) => (v == null ? '—' : `${v.toFixed(d)}%`);
const days = (v) => (v == null ? '—' : `${v.toFixed(1)} d`);

export default function Transshipment({ optimizationState = null }) {
  const ts = useTransshipment(optimizationState);
  const m = ts.model;
  const t = m?.totals;
  const eng = ts.engine;
  const transit = ts.ledger?.strategy_report?.extended_metrics?.transit_time_days || null;
  const services = optimizationState?.global?.selected_services || [];
  const [hubCode, setHubCode] = useState(null);
  const [showAllHubs, setShowAllHubs] = useState(false);
  const hub = m?.hubs.find((h) => h.code === hubCode) || m?.hubs[0] || null;
  const hubServices = useMemo(() => (hub ? services.filter((s) => hub.services.includes(String(s.id))) : services), [hub, services]);
  const mapPrefs = useMapPrefs();
  const maxTeu = m?.hubs[0]?.teu || 1;
  const hubs = m ? (showAllHubs ? m.hubs : m.hubs.slice(0, HUBS_SHOWN)) : [];
  const costKnown = t?.cost != null;
  const name = (code) => getPortName(code) || m?.hubs.find((h) => h.code === code)?.name || '';

  const exportHubs = () => downloadCsv('transshipment_hubs', [
    ['port', (h) => h.code], ['name', (h) => name(h.code)], ['transfer TEU / week', (h) => Math.round(h.teu)],
    ['share of transfer moves %', (h) => h.shareOfMoves], ['cost per TEU (USD)', (h) => h.costPerTeu],
    ['cost per week (USD)', (h) => (h.cost == null ? '' : Math.round(h.cost))], ['services', (h) => h.services.join(' ')],
    ['service connections', (h) => h.pairs.length], ['OD flows', (h) => h.flows],
  ], m.hubs);
  const exportLanes = () => downloadCsv('transshipped_lanes', [
    ['origin', (l) => l.o], ['destination', (l) => l.d], ['TEU / week', (l) => Math.round(l.teu)], ['via', (l) => l.via.join(' ')],
    ['services', (l) => l.services.join(' → ')], ['transshipment cost / week (USD)', (l) => (l.cost == null ? '' : Math.round(l.cost))],
  ], m.lanes);

  return (
    <div className="cx-page-body space-y-3">
      <PageHead
        section="Network"
        eyebrow="Transshipment"
        title="Where cargo changes ship, and what it costs"
        subtitle="Cargo that no single service carries from its origin to its destination is unloaded at a hub and loaded onto another service. Each transfer pays the hub's transshipment charge per TEU and adds waiting time. Figures are the routed flows of the plan on screen, priced with the dataset's port tariffs."
        pills={[
          { tone: m ? 'available' : 'no_data', label: m ? `${fmtNum(t.flows)} of ${fmtNum(ts.ledger.plan.flows.length)} routed flows transfer` : 'no routed flows' },
          { tone: ts.status === 'ok' ? 'available' : ts.status === 'loading_tariffs' ? 'active' : 'no_data',
            label: ts.status === 'ok' ? 'port tariffs: dataset' : ts.status === 'loading_tariffs' ? 'loading tariffs…' : ts.status === 'no_tariffs' ? 'tariffs need the backend' : 'no ledger for this plan' },
        ]}
      />

      {!m && (
        <p className="dz-warn">This plan has no routed flows of its own (no ledger whose services match the plan on screen), so where cargo changes ship is not known. Pick a run in the header that has a network ledger.</p>
      )}

      {m && (
        <>
          <div className="em-kpis">
            <div className="em-kpi"><span>Transshipped cargo</span><b>{fmtNum(Math.round(t.transferTeu))} TEU/wk</b><i>{pct(t.share)} of {fmtNum(Math.round(t.servedTeu))} TEU carried · {fmtNum(t.flows)} OD flows</i><SourceChip src="Engine ledger flows" def="TEU of flows riding 2+ services" /></div>
            <div className="em-kpi"><span>Transshipment cost</span><b>{costKnown ? fmtUsd(t.cost) : ts.ledger?.weekly_usd?.transshipment_cost != null ? fmtUsd(ts.ledger.weekly_usd.transshipment_cost) : '—'}/wk</b>
              <i>{m.check.matches === true ? 'equals the ledger’s transshipment line' : m.check.matches === false ? `ledger says ${fmtUsd(m.check.ledger)}` : costKnown ? '' : 'ledger total; per-hub split needs the tariffs'}{ts.ledger?.weekly_usd?.total_operating_cost ? ` · ${pct((ts.ledger.weekly_usd.transshipment_cost / ts.ledger.weekly_usd.total_operating_cost) * 100)} of costs` : ''}</i>
              <SourceChip src="Ledger × port tariffs" def="Σ transfer TEU × hub transshipment $/TEU" /></div>
            <div className="em-kpi"><span>Cost per transfer</span><b>{t.costPerMove != null ? `${fmtUsd(t.costPerMove)}/TEU` : '—'}</b><i>{fmtNum(Math.round(t.moves))} transfer moves/wk{t.twoPlus ? ` · ${fmtNum(Math.round(t.twoPlus))} TEU transfer twice` : ' · none transfers twice'}</i><SourceChip src="Ledger × port tariffs" def="cost ÷ transfer moves (TEU)" /></div>
            <div className="em-kpi"><span>Transfer hubs</span><b>{t.hubs}</b><i>top 3 handle {pct(t.top3Share, 0)} of moves{m.hubs[0] ? ` · busiest ${m.hubs[0].code}` : ''}</i><SourceChip src="Engine ledger flows" def="ports where a routed flow changes service" /></div>
            {transit?.mean_transshipped != null && (
              <div className="em-kpi"><span>Transit, transshipped vs direct</span><b>{days(transit.mean_transshipped)} vs {days(transit.mean_direct)}</b><i>+{days(transit.mean_transshipped - transit.mean_direct)} per box; {days(ts.assumptions.transfer_wait_days)} wait per transfer</i><SourceChip src="Engine strategy report" def="TEU-weighted mean transit days" /></div>
            )}
            {eng?.teu_by_type && (
              <div className="em-kpi"><span>Kind of transfer</span><b>{pct(eng.teu ? (eng.teu_by_type.feeder / eng.teu) * 100 : null, 0)} feeder</b><i>{fmtNum(eng.teu_by_type.feeder)} feeder · {fmtNum(eng.teu_by_type.hub_and_spoke)} hub-and-spoke · {fmtNum(eng.teu_by_type.multi_hop)} multi-hop TEU</i><SourceChip src="Engine strategy report" def="engine’s classification of transfer paths" /></div>
            )}
          </div>
          {ts.status === 'no_tariffs' && <p className="dz-warn">Port tariffs come from the backend (/api/datasets/…/demand); until it answers the TEU figures are complete but the cost per hub is not shown.</p>}

          <div className="grid grid-cols-12 gap-3 items-start">
            <div className="col-span-12 xl:col-span-7 min-w-0">
              <InstrumentPanel title="Transfer hubs"
                right={<span className="flex gap-2 items-center"><span className="text-[12px] text-slate-400">click a hub for its connections</span><button type="button" className="cmp-btn" onClick={exportHubs}>CSV</button></span>}
                bodyPadding="flush">
                <div className="tf-scroll">
                  <table className="viz-table wi-table tf-table ts-table">
                    <thead><tr><th>Hub</th><th>Transfer TEU / week</th><th className="r">$ / TEU</th><th className="r">Cost / week</th><th className="r">Services</th></tr></thead>
                    <tbody>
                      {hubs.map((h) => (
                        <tr key={h.code} className={`ts-row${hub?.code === h.code ? ' is-sel' : ''}`} tabIndex={0} aria-selected={hub?.code === h.code}
                          onClick={() => setHubCode(h.code)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setHubCode(h.code); } }}>
                          <td><b>{h.code}</b><div className="dz-pct">{name(h.code)}</div></td>
                          <td>
                            <div className="ts-barcell">
                              <span className="ts-bar" style={{ width: `${(h.teu / maxTeu) * 100}%` }} aria-hidden="true" />
                              <span className="ts-val">{fmtNum(Math.round(h.teu))}<span className="dz-pct"> · {pct(h.shareOfMoves)}</span></span>
                            </div>
                          </td>
                          <td className="r">{h.costPerTeu != null ? fmtUsd(h.costPerTeu) : '—'}</td>
                          <td className="r">{h.cost != null ? fmtUsd(h.cost) : '—'}{h.shareOfCost != null && <div className="dz-pct">{pct(h.shareOfCost)} of cost</div>}</td>
                          <td className="r">{h.services.length}<div className="dz-pct">{h.pairs.length} connection{h.pairs.length === 1 ? '' : 's'}</div></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {m.hubs.length > HUBS_SHOWN && (
                  <div className="px-3 py-2"><button type="button" className="cmp-btn" onClick={() => setShowAllHubs((v) => !v)}>{showAllHubs ? `Show top ${HUBS_SHOWN}` : `Show all ${m.hubs.length} hubs`}</button></div>
                )}
              </InstrumentPanel>
            </div>

            <div className="col-span-12 xl:col-span-5 min-w-0">
              {hub && (
                <InstrumentPanel title={`${hub.code} ${name(hub.code)}`} right={<span className="text-[12px] text-slate-400">{fmtNum(Math.round(hub.teu))} TEU/wk change ship here</span>}>
                  <div className="ts-hubhead">
                    <div><span>Tariff</span><b>{hub.costPerTeu != null ? `${fmtUsd(hub.costPerTeu)}/TEU` : '—'}</b></div>
                    <div><span>Cost / week</span><b>{hub.cost != null ? fmtUsd(hub.cost) : '—'}</b></div>
                    <div><span>OD flows</span><b>{hub.flows}</b></div>
                  </div>
                  <div className="ts-sub">Service connections <span className="dz-pct">· arriving on → leaving on</span></div>
                  <ul className="ts-list">
                    {hub.pairs.slice(0, 10).map((p) => (
                      <li key={`${p.from}-${p.to}`}><span>{p.from} <span className="dz-pct">→</span> {p.to}</span><b>{fmtNum(Math.round(p.teu))} TEU</b></li>
                    ))}
                    {hub.pairs.length > 10 && <li className="dz-pct">+{hub.pairs.length - 10} more</li>}
                  </ul>
                  <div className="ts-sub">Cargo lanes through {hub.code}</div>
                  <ul className="ts-list">
                    {hub.lanes.slice(0, 8).map((l) => (
                      <li key={`${l.o}-${l.d}-${l.services.join()}`}>
                        <span>{l.o} → {l.d}<span className="dz-pct"> · via {l.via.join(', ')}</span></span>
                        <b>{fmtNum(Math.round(l.teu))} TEU</b>
                      </li>
                    ))}
                    {hub.lanes.length > 8 && <li className="dz-pct">+{hub.lanes.length - 8} more lanes</li>}
                  </ul>
                </InstrumentPanel>
              )}
            </div>
          </div>

          <InstrumentPanel title={hub ? `Services connecting at ${hub.code}` : 'On the map'}
            right={!mapPrefs.layers.hubs ? <button type="button" className="cmp-btn" onClick={() => setMapPrefs({ layers: { hubs: true } })}>Show transfer hubs</button> : <span className="text-[12px] text-slate-400">rings = transfer hubs, area ∝ TEU · toggle in Layers</span>}
            bodyPadding="flush">
            <div style={{ height: 440 }}>
              <WorldMap optimizationState={optimizationState} selectedServices={hubServices} focusPort={hub?.code || null} dataset={ts.dataset}
                drawKey={`transship|${hub?.code || ''}`} />
            </div>
          </InstrumentPanel>

          <InstrumentPanel title="Transshipped cargo lanes" right={<span className="flex gap-2 items-center"><span className="text-[12px] text-slate-400">largest first</span><button type="button" className="cmp-btn" onClick={exportLanes}>CSV</button></span>} bodyPadding="flush">
            <div className="tf-scroll">
              <table className="viz-table wi-table tf-table ts-table">
                <thead><tr><th>Origin → destination</th><th className="r">TEU / week</th><th>Changes ship at</th><th>Services ridden</th><th className="r">Transshipment / week</th></tr></thead>
                <tbody>
                  {m.lanes.slice(0, LANES_SHOWN).map((l) => (
                    <tr key={`${l.o}-${l.d}-${l.services.join()}`}>
                      <td>{l.o} → {l.d}<div className="dz-pct">{name(l.o)} → {name(l.d)}</div></td>
                      <td className="r">{fmtNum(Math.round(l.teu))}</td>
                      <td>{l.via.map((c) => <button key={c} type="button" className="ts-chip" onClick={() => setHubCode(c)} title={`Show ${c} ${name(c)}`}>{c}</button>)}</td>
                      <td className="dz-pct">{l.services.join(' → ')}</td>
                      <td className="r">{l.cost != null ? fmtUsd(l.cost) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="viz-note px-3 pb-3">Top {Math.min(LANES_SHOWN, m.lanes.length)} of {m.lanes.length} transshipped flows; the CSV has all of them.</p>
          </InstrumentPanel>

          <InstrumentPanel title="Method">
            <ul className="viz-note ws-method">
              <li>A routed flow is a list of segments (service, from, to). Where one segment ends and the next begins, the cargo changes ship: that port is a transfer hub for the flow.</li>
              <li>Cost at a hub = TEU transferred there × the hub’s transshipment charge per TEU from the dataset. This is the engine ledger’s rule, so the hubs add up to the ledger’s weekly transshipment cost{m.check.matches === true ? ` (${fmtUsd(m.check.computed)}, checked)` : ''}. Loading at the origin and discharge at the destination are handling costs, not transshipment.{m.hubs.some((h) => h.costPerTeu === 0) ? ` The dataset gives ${m.hubs.filter((h) => h.costPerTeu === 0).map((h) => h.code).join(', ')} a transshipment charge of $0, so transfers there cost nothing.` : ''}</li>
              <li>A box that transfers twice pays twice and counts as two moves. The engine allows at most {ts.assumptions.max_transfers_per_od ?? 2} transfers per path, needs {ts.assumptions.transshipment_min_hours ?? '—'} h at the hub and adds {ts.assumptions.transfer_wait_days ?? '—'} days of waiting per transfer to the transit time.</li>
            </ul>
          </InstrumentPanel>
        </>
      )}

      <Provenance
        source="network_ledger.plan.flows (routed segments) × /api/datasets/<dataset>/demand port tariffs; transit days and transfer kinds from network_ledger.strategy_report"
        sourceStatus={m ? 'available' : 'no_data'}
        attribution="Read-only view of the recorded plan"
        license="Internal artifact"
      />
    </div>
  );
}
