/**
 * PortDetailPanel.jsx
 * -------------------
 * Port drill-down for Network Intelligence: what the plan does at one port.
 *
 * - Services calling (click one to inspect it) and calls per week.
 * - Cargo out / in: TEU the plan carries from and to the port, against the lane demand of the dataset.
 * - Transshipment: TEU changing ship here (flows whose path transfers at this port).
 * - Unserved: demand from / to the port the plan leaves uncarried, and its largest lanes.
 * - Port tariffs from the dataset (handling, call, transshipment cost; draft).
 *
 * Figures come from utils/portFlows.portActivity (routed flows of the run's ledger + the dataset's demand).
 * Without the backend the demand side is unknown: those rows say so instead of showing zeros.
 */

import React from 'react';
import { getPortName } from '../../utils/portLookup.js';
import { portGeoRegion } from '../../utils/geoRegion.js';
import { fmtNum, fmtUsd } from '../../utils/formatters.js';

const LANES_SHOWN = 6;

function ServedBar({ served, demand, label }) {
  const pct = demand > 0 ? Math.min(100, (served / demand) * 100) : null;
  return (
    <div className="pd-row">
      <div className="flex justify-between gap-2">
        <span className="text-slate-400">{label}</span>
        <span className="text-slate-100 font-semibold">
          {fmtNum(served)}{demand != null && <span className="text-slate-400 font-normal"> / {fmtNum(demand)} TEU</span>}
        </span>
      </div>
      {pct != null && (
        <div className="pd-bar" role="img" aria-label={`${pct.toFixed(0)}% of demand carried`}>
          <span style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}

export default function PortDetailPanel({ code, activity, tariffs = null, onInspectService, onOpenPort, onClose }) {
  if (!code) return null;
  const p = activity?.ports.get(code) || null;
  const hasDemand = Boolean(activity?.hasDemand);
  const services = p ? [...p.services].sort((a, b) => Number(b.frequency_per_week || 0) - Number(a.frequency_per_week || 0)) : [];
  const lanes = p ? p.unservedLanes.slice(0, LANES_SHOWN) : [];
  const unserved = p ? p.unservedOut + p.unservedIn : 0;
  const t = tariffs?.[code];

  return (
    <div className="p-3 font-mono text-[12px] leading-tight space-y-3">
      <div className="flex justify-between items-start pb-2 border-b border-white/10 gap-2">
        <div className="min-w-0">
          <div className="text-xs font-bold text-white tracking-wider">{code}</div>
          <div className="text-slate-300 truncate">{getPortName(code)}</div>
          <div className="text-slate-400">{portGeoRegion(code) || 'region unknown'}</div>
        </div>
        {onClose && (
          <button type="button" onClick={onClose} className="text-[12px] px-2 py-1 rounded bg-white/5 hover:bg-white/15 border border-white/10 text-slate-300 hover:text-white">
            ✕ CLOSE
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-1.5">
        <div className="bg-white/[0.02] p-2 border border-white/5">
          <div className="text-slate-400 uppercase tracking-wider">Services</div>
          <div className="text-sm font-bold text-slate-100 mt-0.5">{services.length}</div>
        </div>
        <div className="bg-white/[0.02] p-2 border border-white/5">
          <div className="text-slate-400 uppercase tracking-wider">Calls / wk</div>
          <div className="text-sm font-bold text-slate-100 mt-0.5">{p ? fmtNum(p.callsPerWeek) : 0}</div>
        </div>
        <div className="bg-white/[0.02] p-2 border border-white/5" title="Demand from or to this port that the plan does not carry">
          <div className="text-slate-400 uppercase tracking-wider">Unserved</div>
          <div className={`text-sm font-bold mt-0.5 ${unserved > 0 ? 'pd-unserved' : 'text-slate-100'}`}>{hasDemand ? fmtNum(unserved) : '—'}</div>
        </div>
      </div>

      <div className="bg-white/[0.02] p-2 border border-white/5 space-y-2">
        <div className="text-slate-400 uppercase tracking-wider font-semibold pb-1 border-b border-white/5">Cargo · TEU / week</div>
        <ServedBar label="Out (export)" served={p?.exportTeu || 0} demand={hasDemand ? p?.demandOut || 0 : null} />
        <ServedBar label="In (import)" served={p?.importTeu || 0} demand={hasDemand ? p?.demandIn || 0 : null} />
        <div className="flex justify-between">
          <span className="text-slate-400" title="TEU whose route changes ship at this port">Transshipped here</span>
          <span className="text-slate-100 font-semibold">{fmtNum(p?.transshipTeu || 0)}</span>
        </div>
        {!hasDemand && <div className="text-slate-400">Demand per lane needs the backend (/api/datasets/…/demand); served cargo is from the run file.</div>}
      </div>

      <div className="bg-white/[0.02] p-2 border border-white/5">
        <div className="flex justify-between text-slate-400 uppercase tracking-wider font-semibold pb-1 mb-1 border-b border-white/5">
          <span>Services calling</span><span>{services.length}</span>
        </div>
        {services.length === 0 ? (
          <div className="text-slate-400">No service of this plan calls here.</div>
        ) : (
          <ul className="space-y-0.5 max-h-40 overflow-y-auto">
            {services.map((s) => (
              <li key={s.id}>
                <button type="button" className="pd-link" onClick={() => onInspectService?.(s)} title={(s.ports || []).join(' → ')}>
                  <span className="font-semibold">{s.id}</span>
                  <span className="text-slate-400"> · {s.frequency_per_week || 1}/wk · {s.vessel_class || '—'}</span>
                  <span className={`ml-auto ${Number(s.weekly_profit) < 0 ? 'text-red-400' : 'text-slate-300'}`}>{fmtUsd(s.weekly_profit)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {hasDemand && (
        <div className="bg-white/[0.02] p-2 border border-white/5">
          <div className="flex justify-between text-slate-400 uppercase tracking-wider font-semibold pb-1 mb-1 border-b border-white/5">
            <span>Largest unserved lanes</span><span>{p?.unservedLanes.length || 0}</span>
          </div>
          {lanes.length === 0 ? (
            <div className="text-slate-400">Every lane from and to this port is fully carried.</div>
          ) : (
            <ul className="space-y-0.5">
              {lanes.map((l) => {
                const other = l.o === code ? l.d : l.o;
                return (
                  <li key={`${l.o}_${l.d}`}>
                    <button type="button" className="pd-link" onClick={() => onOpenPort?.(other)} title={`Open ${getPortName(other)}`}>
                      <span>{l.o === code ? '→' : '←'} {other}</span>
                      <span className="text-slate-400 truncate"> {getPortName(other)}</span>
                      <span className="ml-auto pd-unserved">{fmtNum(l.teu)}{l.teu < l.demand ? <span className="text-slate-400"> / {fmtNum(l.demand)}</span> : null}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {t && (
        <div className="bg-white/[0.02] p-2 border border-white/5 space-y-1">
          <div className="text-slate-400 uppercase tracking-wider font-semibold pb-1 border-b border-white/5">Port tariffs (dataset)</div>
          <div className="flex justify-between"><span className="text-slate-400">Handling / TEU</span><span className="text-slate-200">{fmtUsd(t.handling_cost)}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Transshipment / TEU</span><span className="text-slate-200">{fmtUsd(t.transshipment_cost)}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Port call (fixed)</span><span className="text-slate-200">{fmtUsd(t.port_call_cost)}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Draft</span><span className="text-slate-200">{t.draft != null ? `${t.draft} m` : '—'}</span></div>
        </div>
      )}
    </div>
  );
}
