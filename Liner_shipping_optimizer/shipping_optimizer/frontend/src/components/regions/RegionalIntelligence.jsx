import { useMemo, useState } from 'react';
import { fmt, fmtNum } from '../../utils/formatters.js';

export default function RegionalIntelligence({ optimizationState }) {
  const [selectedRegionId, setSelectedRegionId] = useState(null);

  const regions = useMemo(() => Object.values(optimizationState.regions), [optimizationState.regions]);
  const sel = regions.find(r => r.id === selectedRegionId) || regions[0];

  if (regions.length === 0) {
    return (
      <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-2">Regional Intelligence</div>
        <div className="text-xs text-white/40 font-mono italic">Not Available</div>
      </div>
    );
  }

  return (
    <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-3">Regional Intelligence</div>

      {/* Region selector tabs */}
      <div className="flex gap-1 mb-3 flex-wrap">
        {regions.map(r => (
          <button key={r.id} onClick={() => setSelectedRegionId(r.id)}
            className="text-[10px] px-2 py-1 rounded font-mono transition-all"
            style={{
              background: (selectedRegionId || regions[0]?.id) === r.id ? `${r.color}18` : "rgba(255,255,255,0.03)",
              border: `1px solid ${(selectedRegionId || regions[0]?.id) === r.id ? `${r.color}44` : "rgba(255,255,255,0.08)"}`,
              color: (selectedRegionId || regions[0]?.id) === r.id ? r.color : "rgba(255,255,255,0.5)",
            }}>
            {r.name}
          </button>
        ))}
      </div>

      {sel && (
        <div className="space-y-3">
          {/* Key metrics */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "Weekly Profit", value: fmt(sel.profit), color: sel.color },
              { label: "Coverage", value: sel.coverage != null ? `${sel.coverage.toFixed(1)}%` : "—", color: sel.color },
              { label: "Margin", value: sel.margin != null ? `${sel.margin.toFixed(1)}%` : "—", color: sel.color },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded p-2 text-center" style={{ background: `${color}08` }}>
                <div className="text-sm font-bold font-mono" style={{ color }}>{value}</div>
                <div className="text-[9px] text-white/40 font-mono">{label}</div>
              </div>
            ))}
          </div>

          {/* Service funnel */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "Generated", value: fmtNum(sel.generated), color: "#888" },
              { label: "Filtered (GA)", value: fmtNum(sel.filtered), color: "#ff9a45" },
              { label: "Selected", value: fmtNum(sel.selected), color: sel.color },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded p-2 text-center" style={{ background: "rgba(255,255,255,0.03)" }}>
                <div className="text-[11px] font-mono font-bold" style={{ color }}>{value}</div>
                <div className="text-[8px] text-white/40 font-mono">{label}</div>
              </div>
            ))}
          </div>

          {/* Hub ports */}
          {sel.hubs && sel.hubs.length > 0 && (
            <div>
              <div className="text-[10px] text-white/30 font-mono uppercase tracking-widest mb-1">Hub Focus</div>
              <div className="flex flex-wrap gap-1">
                {sel.hubs.slice(0, 5).map(h => (
                  <span key={h} className="text-[9px] px-1.5 py-0.5 rounded font-mono" style={{ background: `${sel.color}15`, color: sel.color, border: `1px solid ${sel.color}30` }}>{h}</span>
                ))}
              </div>
            </div>
          )}

          {/* Strategy */}
          {sel.strategy && (
            <div>
              <div className="text-[10px] text-white/30 font-mono uppercase tracking-widest mb-1">AI Strategy</div>
              <div className="text-[10px] text-white/50 font-mono leading-relaxed">
                {sel.strategy.slice(0, 150)}{sel.strategy.length > 150 ? "..." : ""}
              </div>
            </div>
          )}

          {/* Cost breakdown brief */}
          {sel.cost != null && (
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded p-1.5" style={{ background: "rgba(255,255,255,0.03)" }}>
                <div className="text-[9px] text-white/30 font-mono">Operating Cost</div>
                <div className="text-[10px] font-mono text-white/60">{fmt(sel.operating_cost || sel.cost)}</div>
              </div>
              <div className="rounded p-1.5" style={{ background: "rgba(255,255,255,0.03)" }}>
                <div className="text-[9px] text-white/30 font-mono">Total Cost</div>
                <div className="text-[10px] font-mono text-white/60">{fmt(sel.cost)}</div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
