import { useMemo } from 'react';
import { computeFleetStats } from '../../utils/fleetStats.js';
import { fmtNum } from '../../utils/formatters.js';

export default function FleetPanel({ optimizationState }) {
  const fleet = useMemo(
    () => computeFleetStats(optimizationState.global.selected_services || []),
    [optimizationState.global.selected_services]
  );

  if (fleet.totalVessels === 0) {
    return (
      <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-2">Fleet Intelligence</div>
        <div className="text-xs text-white/40 font-mono italic">Not Available</div>
      </div>
    );
  }

  return (
    <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-3">Fleet Intelligence</div>

      <div className="grid grid-cols-4 gap-3 mb-3">
        {[
          { label: "Vessels Deployed", value: fmtNum(fleet.totalVessels), color: "#00d4ff" },
          { label: "Capacity Deployed", value: `${(fleet.totalCapacity / 1000).toFixed(0)}K TEU`, color: "#10b981" },
          { label: "Total Load", value: `${(fleet.totalLoad / 1000).toFixed(0)}K TEU`, color: "#8b5cf6" },
          { label: "Utilization", value: `${fleet.utilizationPct}%`, color: "#f59e0b" },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-lg p-2 text-center" style={{ background: `${color}08`, border: `1px solid ${color}22` }}>
            <div className="text-lg font-bold font-mono" style={{ color }}>{value}</div>
            <div className="text-[9px] text-white/40 font-mono uppercase tracking-wider">{label}</div>
          </div>
        ))}
      </div>

      <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-2">Vessel Class Distribution</div>
      <div className="space-y-1.5">
        {fleet.vesselClassList.map(({ cls, count, pct }) => (
          <div key={cls}>
            <div className="flex justify-between text-[10px] mb-0.5">
              <span className="text-white/60 font-mono">{cls}</span>
              <span className="text-white/80 font-mono">{count} <span className="text-white/30">({pct}%)</span></span>
            </div>
            <div className="w-full h-1 rounded-full bg-white/5 overflow-hidden">
              <div className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, background: "linear-gradient(90deg, rgba(0,212,255,0.5), #00d4ff)" }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
