import { useState, useEffect } from 'react';
import ProgressBar from '../common/ProgressBar.jsx';
import { fmt, fmtNum, parseStrategyCode, parseStrategyReasons } from '../../utils/formatters.js';
import RegionCard from './RegionCard.jsx';

export default function RegionDetails({ optimizationState }) {
  const regions = Object.values(optimizationState.regions);
  const [selId, setSelId] = useState(null);

  useEffect(() => {
    if (!selId && regions.length > 0) {
      setSelId(regions[0].id);
    }
  }, [regions, selId]);

  const sel = regions.find(r => r.id === selId) || regions[0];

  if (regions.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-white/40">No regional data available</div>
      </div>
    );
  }

  return (
    <div className="flex gap-6 h-full">
      <div className="grid grid-cols-1 gap-3 w-80 flex-shrink-0 overflow-y-auto pr-1">
        {regions.map(r => <RegionCard key={r.id} r={r} onClick={() => setSelId(r.id)} selected={selId === r.id} />)}
      </div>
      <div className="flex-1 rounded-xl p-5 overflow-y-auto" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
        {sel && regions.length > 0 && (
          <div>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: sel.color, boxShadow: `0 0 12px ${sel.color}` }} />
              <h2 className="text-lg font-semibold text-white" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>{sel.name} Regional Agent</h2>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-6">
              {[
                { label: "Weekly Profit", value: fmt(sel.profit), color: sel.color },
                { label: "Annual Profit", value: fmt(sel.annualProfit ?? sel.profit * 52), color: "#10b981" },
                { label: "Operating Cost", value: fmt(sel.operating_cost ?? sel.cost), color: "#f59e0b" },
                { label: "Uncovered TEU", value: fmtNum(sel.uncovered ?? sel.unservedDemand ?? 0), color: "#ef4444" },
              ].map(({ label, value, color }) => (
                <div key={label} className="rounded-lg p-4" style={{ background: `${color}08`, border: `1px solid ${color}22` }}>
                  <div className="text-xs text-white/40 mb-1 font-mono">{label}</div>
                  <div className="text-xl font-bold font-mono" style={{ color }}>{value}</div>
                </div>
              ))}
            </div>

            <div className="mb-6">
              <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-3">Cost Breakdown</div>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Base Operating Cost", value: fmt(sel.operating_cost || sel.cost), color: "#f59e0b" },
                  { label: "Transshipment Cost", value: fmt(sel.transship_cost || 0), color: "#f59e0b" },
                  { label: "Total Weekly Cost", value: fmt(sel.cost), color: "#ef4444" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
                    <div className="text-[10px] text-white/40 mb-1 font-mono uppercase tracking-wider">{label}</div>
                    <div className="text-lg font-bold font-mono text-white/80">{value}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mb-5">
              <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-3">Service Funnel</div>
              {(() => {
                const gen = sel.generated || 1;
                const fltPct = ((sel.filtered / gen) * 100).toFixed(0);
                const selPct = ((sel.selected / gen) * 100).toFixed(0);

                return (
                  <div className="flex flex-col gap-2 max-w-md">
                    <div className="flex flex-col items-center">
                      <div className="flex justify-between w-full text-xs text-white/50 px-1 font-mono">
                        <span>Generated Services</span>
                        <span>{fmtNum(sel.generated)}</span>
                      </div>
                      <div className="w-full h-6 rounded bg-white/10 flex items-center justify-center relative overflow-hidden mt-1">
                        <div className="absolute inset-0 transition-all duration-1000" style={{ background: `linear-gradient(90deg, ${sel.color}22, ${sel.color}44)` }} />
                        <span className="text-xs font-mono text-white/95 z-10 font-bold">100%</span>
                      </div>
                    </div>

                    <div className="flex flex-col items-center">
                      <div className="flex justify-between w-full text-xs text-white/50 px-1 font-mono">
                        <span>Filtered Services (GA Pass)</span>
                        <span>{fmtNum(sel.filtered)}</span>
                      </div>
                      <div className="w-full h-6 rounded bg-white/5 flex items-center justify-center relative overflow-hidden mt-1">
                        <div className="h-full transition-all duration-1000" style={{ width: `${fltPct}%`, background: `linear-gradient(90deg, ${sel.color}33, ${sel.color}66)` }} />
                        <span className="absolute text-xs font-mono text-white/95 z-10 font-bold">{fltPct}%</span>
                      </div>
                    </div>

                    <div className="flex flex-col items-center">
                      <div className="flex justify-between w-full text-xs text-white/50 px-1 font-mono">
                        <span>Selected Services (MILP Optimal)</span>
                        <span>{fmtNum(sel.selected)}</span>
                      </div>
                      <div className="w-full h-6 rounded bg-white/5 flex items-center justify-center relative overflow-hidden mt-1">
                        <div className="h-full transition-all duration-1000" style={{ width: `${selPct}%`, background: `linear-gradient(90deg, ${sel.color}88, ${sel.color})`, boxShadow: `0 0 12px ${sel.color}66` }} />
                        <span className="absolute text-xs font-mono text-white/95 z-10 font-bold">{selPct}%</span>
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>

            <div className="mb-5">
              <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-3">Hub Ports</div>
              <div className="flex flex-wrap gap-2">
                {sel.hubs.map(h => (
                  <div key={h} className="px-3 py-1.5 rounded-lg text-sm font-mono" style={{ background: `${sel.color}15`, color: sel.color, border: `1px solid ${sel.color}33` }}>
                    {h}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-lg p-4" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-3">Optimization Strategy</div>
              {sel.strategy ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: sel.color }} />
                    <span className="text-sm font-bold font-mono" style={{ color: sel.color }}>{parseStrategyCode(sel.strategy)}</span>
                  </div>
                  {parseStrategyReasons(sel.strategy).length > 0 ? (
                    <div className="space-y-1.5">
                      {parseStrategyReasons(sel.strategy).map((reason, i) => (
                        <div key={i} className="flex items-start gap-2">
                          <span className="text-[10px] font-mono mt-0.5 flex-shrink-0" style={{ color: sel.color }}>R{i+1}</span>
                          <span className="text-xs text-white/60 font-mono leading-relaxed">{reason}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-white/50 font-mono leading-relaxed">{sel.strategy}</p>
                  )}
                </div>
              ) : (
                <div className="text-sm text-white/40 font-mono italic">Strategy from optimizer not available</div>
              )}
              {sel.explanation && (
                <div className="mt-3 pt-3 border-t border-white/5">
                  <div className="text-[10px] text-white/30 font-mono uppercase tracking-widest mb-1">Region Report</div>
                  <p className="text-xs text-white/50 font-mono leading-relaxed">{sel.explanation.slice(0, 200)}{sel.explanation.length > 200 ? "..." : ""}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
