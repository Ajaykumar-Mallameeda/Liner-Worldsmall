/**
 * ServiceDetailPanel.jsx
 * ----------------------
 * Right-side Service Inspection Panel for Network Intelligence.
 * Exposes full runtime financial, operational, and port telemetry
 * for a single selected service directly from pipeline_output.json.
 */

import React from 'react';
import { getPortName, getPortFullLabel, getPortCoordinates } from '../../utils/portLookup.js';
import { getRegionColor } from '../map/WorldMap.jsx';
import { fmtNum, fmtPct, fmtUsd } from '../../utils/formatters.js';
import { legScheduleOf } from '../../utils/legTimes.js';

/**
 * One rotation laid out in time: a bar of sail days (per leg) and port stays across the declared cycle, then
 * the legs with distance, sail days and weekly load against weekly capacity (capacity × departures per week).
 * Runs without per-leg times get the distance-split estimate, labelled as such.
 */
function VoyageTimeline({ service }) {
  const sch = legScheduleOf(service, getPortCoordinates);
  if (!sch) return null;
  const weeklyCap = (Number(service.capacity) || 0) * (Number(service.frequency_per_week) || 1);
  const fromRun = sch.source === 'run';
  const segs = [];
  sch.legs.forEach((l, i) => {
    segs.push({ key: `s${i}`, kind: 'sail', days: l.sailDays, tip: `${l.from} → ${l.to}: ${l.sailDays.toFixed(1)} days at sea` });
    segs.push({ key: `p${i}`, kind: 'port', days: sch.stayDays, tip: `${l.to}: ${sch.stayDays.toFixed(1)} day${sch.stayDays === 1 ? '' : 's'} in port` });
  });
  if (sch.slackDays > 0.05) segs.push({ key: 'slack', kind: 'slack', days: sch.slackDays, tip: `${sch.slackDays.toFixed(1)} days of schedule slack (whole-day cycle)` });
  const sea = sch.legs.reduce((a, l) => a + l.sailDays, 0);
  return (
    <div className="bg-white/[0.02] p-2 border border-white/5">
      <div className="flex justify-between items-center mb-1.5 pb-1 border-b border-white/5 gap-2">
        <span className="text-[12px] text-slate-400 uppercase tracking-wider font-semibold">VOYAGE TIMELINE</span>
        <span className={`vt-src ${fromRun ? 'is-run' : ''}`} title={fromRun
          ? "Sail days and port stays recorded by the engine's ledger for this run."
          : 'This run predates per-leg times: sea time (cycle minus a 24 h stay per call) is split over the legs by great-circle distance.'}>
          {fromRun ? 'run leg times' : 'estimated'}
        </span>
      </div>
      <div className="vt-bar" role="img" aria-label={`${sea.toFixed(1)} days at sea, ${(sch.stayDays * sch.legs.length).toFixed(1)} in port${sch.slackDays > 0.05 ? `, ${sch.slackDays.toFixed(1)} slack` : ''}, cycle ${sch.cycleDays} days`}>
        {segs.map((sg) => <span key={sg.key} className={`vt-seg is-${sg.kind}`} style={{ flexGrow: sg.days }} title={sg.tip} />)}
      </div>
      <div className="flex justify-between text-[12px] text-slate-400 mt-1 mb-1.5 flex-wrap gap-x-3">
        <span><span className="vt-key is-sail" aria-hidden="true" />sea {sea.toFixed(1)} d</span>
        <span><span className="vt-key is-port" aria-hidden="true" />port {(sch.stayDays * sch.legs.length).toFixed(1)} d</span>
        {sch.slackDays > 0.05 && <span><span className="vt-key is-slack" aria-hidden="true" />slack {sch.slackDays.toFixed(1)} d</span>}
        <span className="text-slate-300">cycle {sch.cycleDays} d</span>
      </div>
      <table className="vt-table">
        <thead>
          <tr><th scope="col">Leg</th><th scope="col">nm</th><th scope="col">Sail d</th><th scope="col" title="Weekly TEU on the leg / weekly capacity">Load</th></tr>
        </thead>
        <tbody>
          {sch.legs.map((l, i) => (
            <tr key={i}>
              <td>{l.from}→{l.to}</td>
              <td>{l.distanceNm != null ? fmtNum(l.distanceNm) : '—'}</td>
              <td>{l.sailDays.toFixed(1)}</td>
              <td>{l.loadTeu != null && weeklyCap > 0 ? `${fmtNum(l.loadTeu)} · ${Math.round((l.loadTeu / weeklyCap) * 100)}%` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ServiceDetailPanel({ service, onClose }) {
  if (!service) return null;

  const regColor = getRegionColor(service.region);
  const ports = service.ports || [];
  const origin = ports[0] || '—';
  const dest = ports[ports.length - 1] || '—';
  const load = service.load || 0;
  const capacity = service.capacity || 1;
  // leg load factor from the ledger (carried TEU-legs / offered TEU-legs); unknown is shown as a dash, never as 0
  const utilPct = service.leg_load_factor != null ? service.leg_load_factor * 100 : null;
  const weeklyProfit = service.weekly_profit || 0;
  const marginPct = service.margin_pct != null ? service.margin_pct : (service.revenue > 0 ? (weeklyProfit / service.revenue) * 100 : 0);

  return (
    <div className="p-3 font-mono text-[12px] leading-tight space-y-3 select-none">
      {/* ── Header: Service ID + Region + Close Button ── */}
      <div className="flex justify-between items-start pb-2 border-b border-white/10">
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: regColor }} />
            <span className="text-xs font-bold text-white tracking-wider">{service.id}</span>
          </div>
          <span
            className="text-[12px] px-1.5 py-0.5 rounded font-bold uppercase tracking-widest"
            style={{ background: `${regColor}20`, color: regColor, border: `1px solid ${regColor}40` }}
          >
            {service.region || '—'}
          </span>
        </div>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="text-[12px] px-2 py-1 rounded bg-white/5 hover:bg-white/15 border border-white/10 text-slate-300 hover:text-white transition-colors"
          >
            ✕ CLEAR
          </button>
        )}
      </div>

      {/* ── Headline KPIs (Profit, Margin, Load, Util) ── */}
      <div className="grid grid-cols-2 gap-1.5">
        <div className="bg-white/[0.02] p-2 border border-white/5">
          <div className="text-[12px] text-slate-400 uppercase tracking-wider">WEEKLY PROFIT</div>
          <div className={`text-sm font-bold mt-0.5 ${weeklyProfit < 0 ? 'text-red-400' : 'text-emerald-400'}`}>
            {fmtUsd(weeklyProfit)}{weeklyProfit < 0 && <span className="cx-loss-chip">LOSS</span>}
          </div>
        </div>
        <div className="bg-white/[0.02] p-2 border border-white/5">
          <div className="text-[12px] text-slate-400 uppercase tracking-wider">PROFIT MARGIN</div>
          <div className="text-sm font-bold text-cyan-400 mt-0.5">{fmtPct(marginPct)}</div>
        </div>
        <div className="bg-white/[0.02] p-2 border border-white/5">
          <div className="text-[12px] text-slate-400 uppercase tracking-wider">WEEKLY CARGO / CAPACITY PER DEPARTURE</div>
          <div className="text-xs font-bold text-slate-100 mt-0.5">
            {fmtNum(load)} <span className="text-slate-400 font-normal">/ {fmtNum(capacity)} TEU</span>
          </div>
        </div>
        <div className="bg-white/[0.02] p-2 border border-white/5">
          <div className="text-[12px] text-slate-400 uppercase tracking-wider">LEG LOAD FACTOR</div>
          <div className="text-xs font-bold text-purple-300 mt-0.5">{utilPct != null ? fmtPct(utilPct) : '—'}</div>
        </div>
      </div>

      {/* ── Port Sequence Timeline ── */}
      <div className="bg-white/[0.02] p-2 border border-white/5">
        <div className="flex justify-between items-center mb-1.5 pb-1 border-b border-white/5">
          <span className="text-[12px] text-slate-400 uppercase tracking-wider font-semibold">PORT SEQUENCE</span>
          <span className="text-[12px] text-cyan-400">{ports.length} PORTS</span>
        </div>
        <div className="space-y-1.5 text-[12px]">
          {ports.map((portCode, idx) => {
            const isOrigin = idx === 0;
            const isDest = idx === ports.length - 1;
            const portName = getPortName(portCode);

            return (
              <div key={idx} className="flex items-center gap-2">
                <span
                  className="w-4 h-4 rounded-full flex items-center justify-center text-[12px] font-bold shrink-0"
                  style={{
                    background: isOrigin ? '#10b981' : isDest ? '#00d4ff' : 'rgba(255,255,255,0.1)',
                    color: isOrigin || isDest ? '#02140d' : '#94a3b8',
                  }}
                >
                  {isOrigin ? 'O' : isDest ? 'D' : idx}
                </span>
                <div className="flex-1 truncate">
                  <span className="font-bold text-slate-100">{portCode}</span>
                  <span className="text-slate-400 text-[12px] ml-1.5">({portName})</span>
                </div>
                {isOrigin && <span className="text-[12px] text-emerald-400 font-semibold">{fmtNum(load)} TEU</span>}
              </div>
            );
          })}
        </div>
      </div>

      <VoyageTimeline service={service} />

      {/* ── Financial Breakdown Table ── */}
      <div className="bg-white/[0.02] p-2 border border-white/5">
        <div className="text-[12px] text-slate-400 uppercase tracking-wider font-semibold mb-1.5 pb-1 border-b border-white/5">
          FINANCIAL BREAKDOWN
        </div>
        <div className="space-y-1 text-[12px]">
          <div className="flex justify-between">
            <span className="text-slate-400">GROSS REVENUE</span>
            <span className="text-slate-200 font-semibold">{fmtUsd(service.revenue)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">TOTAL OPERATING COST</span>
            <span className="text-amber-300 font-semibold">{fmtUsd(service.cost)}</span>
          </div>
          <div className="flex justify-between pl-2 border-l border-white/10 text-[12px] text-slate-400">
            <span>• VESSEL CHARTER</span>
            <span>{fmtUsd(service.vessel_cost)}</span>
          </div>
          <div className="flex justify-between pl-2 border-l border-white/10 text-[12px] text-slate-400">
            <span>• FUEL COST</span>
            <span>{fmtUsd(service.fuel_cost)}</span>
          </div>
          <div className="flex justify-between pl-2 border-l border-white/10 text-[12px] text-slate-400">
            <span>• PORT DUES / HANDLING</span>
            <span>{fmtUsd(service.port_cost)}</span>
          </div>
        </div>
      </div>

      {/* ── Vessel Specifications ── */}
      <div className="bg-white/[0.02] p-2 border border-white/5 text-[12px]">
        <div className="text-[12px] text-slate-400 uppercase tracking-wider font-semibold mb-1 pb-1 border-b border-white/5">
          VESSEL SPECIFICATION
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">VESSEL CLASS</span>
          <span className="text-slate-100 font-semibold">{service.vessel_class || '—'}</span>
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-slate-400">REGION (BY PORTS)</span>
          <span className="font-semibold" style={{ color: regColor }}>{service.region || '—'}</span>
        </div>
        {service.agent_region && (
          <div className="flex justify-between mt-1" title="The optimizer's regional agent that generated this service. Agent names are cluster labels and may not match geography.">
            <span className="text-slate-400">PLANNED BY AGENT</span>
            <span className="text-slate-200 font-semibold">{service.agent_region}</span>
          </div>
        )}
        {(service.regions_touched || []).length > 1 && (
          <div className="flex justify-between mt-1">
            <span className="text-slate-400">CALLS IN</span>
            <span className="text-slate-200 font-semibold text-right">{service.regions_touched.join(', ')}</span>
          </div>
        )}
      </div>
    </div>
  );
}
