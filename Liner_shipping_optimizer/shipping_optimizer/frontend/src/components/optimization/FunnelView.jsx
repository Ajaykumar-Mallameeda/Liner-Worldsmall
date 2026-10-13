import ProgressBar from '../common/ProgressBar.jsx';
import { fmt, fmtNum } from '../../utils/formatters.js';

export default function FunnelView({ optimizationState }) {
  const regions = Object.values(optimizationState.regions);

  const totalGenerated = regions.reduce((s, r) => s + (r.generated || 0), 0);
  const totalFiltered = regions.reduce((s, r) => s + (r.filtered || 0), 0);
  const totalSelected = regions.reduce((s, r) => s + (r.selected || 0), 0);
  const filtPct = totalGenerated > 0 ? ((totalFiltered / totalGenerated) * 100).toFixed(1) : 0;
  const selPct = totalGenerated > 0 ? ((totalSelected / totalGenerated) * 100).toFixed(1) : 0;

  return (
    <div className="space-y-5">
      <div className="rounded-xl p-6" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-5">Global Service Selection Pyramid · All Regions Combined</div>
        <div className="flex flex-col items-center gap-0 max-w-xl mx-auto">
          <div className="flex flex-col items-center w-full">
            <div className="flex justify-between w-full text-xs text-white/60 px-2 font-mono mb-1">
              <span className="font-semibold text-white/80">① Generated Services</span>
              <span className="font-bold text-white">{fmtNum(totalGenerated)} <span className="text-white/40">— 100%</span></span>
            </div>
            <div className="w-full h-10 rounded-lg bg-white/10 flex items-center justify-center relative overflow-hidden" style={{ background: "linear-gradient(90deg, rgba(0,212,255,0.15), rgba(0,212,255,0.3))" }}>
              <span className="text-sm font-bold font-mono text-white/90">100% — All Candidate Services</span>
            </div>
          </div>

          <div className="text-white/20 text-xl my-1">▼</div>

          <div className="flex flex-col items-center" style={{ width: `${Math.max(40, filtPct)}%`, minWidth: 220 }}>
            <div className="flex justify-between w-full text-xs text-white/60 px-2 font-mono mb-1">
              <span className="font-semibold text-white/80">② Filtered (GA Pass)</span>
              <span className="font-bold" style={{ color: "#10b981" }}>{fmtNum(totalFiltered)} <span className="text-white/40">— {filtPct}%</span></span>
            </div>
            <div className="w-full h-9 rounded-lg flex items-center justify-center relative overflow-hidden" style={{ background: "linear-gradient(90deg, rgba(16,185,129,0.2), rgba(16,185,129,0.4))", border: "1px solid rgba(16,185,129,0.3)" }}>
              <span className="text-sm font-bold font-mono" style={{ color: "#10b981" }}>{filtPct}% pass GA filter</span>
            </div>
          </div>

          <div className="text-white/20 text-xl my-1">▼</div>

          <div className="flex flex-col items-center" style={{ width: `${Math.max(25, selPct)}%`, minWidth: 160 }}>
            <div className="flex justify-between w-full text-xs text-white/60 px-2 font-mono mb-1">
              <span className="font-semibold text-white/80">③ Selected (MILP)</span>
              <span className="font-bold" style={{ color: "#f59e0b" }}>{fmtNum(totalSelected)} <span className="text-white/40">— {selPct}%</span></span>
            </div>
            <div className="w-full h-8 rounded-lg flex items-center justify-center relative overflow-hidden" style={{ background: "linear-gradient(90deg, rgba(245,158,11,0.3), rgba(245,158,11,0.6))", border: "1px solid rgba(245,158,11,0.4)", boxShadow: "0 0 20px rgba(245,158,11,0.2)" }}>
              <span className="text-sm font-bold font-mono" style={{ color: "#f59e0b" }}>{selPct}% MILP optimal</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-5">
          {[
            { label: "Total Generated", value: fmtNum(totalGenerated), color: "#00d4ff", sub: "candidate services" },
            { label: "After GA Filter", value: fmtNum(totalFiltered), color: "#10b981", sub: `${filtPct}% retained`, pct: filtPct },
            { label: "MILP Selected", value: fmtNum(totalSelected), color: "#f59e0b", sub: `${selPct}% of generated`, pct: selPct },
          ].map(({ label, value, color, sub }) => (
            <div key={label} className="rounded-lg p-4 text-center" style={{ background: `${color}08`, border: `1px solid ${color}22` }}>
              <div className="text-xs text-white/40 font-mono mb-1">{label}</div>
              <div className="text-2xl font-bold font-mono" style={{ color }}>{value}</div>
              <div className="text-xs text-white/40 mt-1 font-mono">{sub}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-5 gap-3">
        {regions.map(r => (
          <div key={r.id} className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: `1px solid ${r.color}33` }}>
            <div className="flex items-center gap-1.5 mb-3">
              <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: r.color }} />
              <span className="text-xs font-mono text-white/70">{r.name}</span>
            </div>
            {(() => {
              const gen = r.generated || 1;
              const fltPct = ((r.filtered / gen) * 100).toFixed(0);
              const selPct = ((r.selected / gen) * 100).toFixed(0);

              return (
                <div className="flex flex-col gap-2 mt-2">
                  <div className="flex flex-col items-center">
                    <div className="flex justify-between w-full text-[10px] text-white/50 px-1 font-mono">
                      <span>Generated</span>
                      <span>{fmtNum(r.generated)}</span>
                    </div>
                    <div className="w-full h-4 rounded bg-white/10 flex items-center justify-center relative overflow-hidden mt-0.5">
                      <div className="absolute inset-0 transition-all duration-1000" style={{ background: `linear-gradient(90deg, ${r.color}22, ${r.color}44)` }} />
                      <span className="text-[10px] font-mono text-white/90 z-10 font-bold">100%</span>
                    </div>
                  </div>

                  <div className="flex flex-col items-center">
                    <div className="flex justify-between w-full text-[10px] text-white/50 px-1 font-mono">
                      <span>Filtered</span>
                      <span>{fmtNum(r.filtered)}</span>
                    </div>
                    <div className="w-full h-4 rounded bg-white/5 flex items-center justify-center relative overflow-hidden mt-0.5">
                      <div className="h-full transition-all duration-1000" style={{ width: `${fltPct}%`, background: `linear-gradient(90deg, ${r.color}33, ${r.color}66)` }} />
                      <span className="absolute text-[10px] font-mono text-white/90 z-10 font-bold">{fltPct}%</span>
                    </div>
                  </div>

                  <div className="flex flex-col items-center">
                    <div className="flex justify-between w-full text-[10px] text-white/50 px-1 font-mono">
                      <span>Selected</span>
                      <span>{fmtNum(r.selected)}</span>
                    </div>
                    <div className="w-full h-4 rounded bg-white/5 flex items-center justify-center relative overflow-hidden mt-0.5">
                      <div className="h-full transition-all duration-1000" style={{ width: `${selPct}%`, background: `linear-gradient(90deg, ${r.color}88, ${r.color})`, boxShadow: `0 0 10px ${r.color}55` }} />
                      <span className="absolute text-[10px] font-mono text-white/90 z-10 font-bold">{selPct}%</span>
                    </div>
                  </div>
                </div>
              );
            })()}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl p-5" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
          <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-4">Profit per Service ($/wk)</div>
          <div className="space-y-2">
            {regions.map(r => {
              const pps = Math.round(r.profit / r.services);
              return (
                <div key={r.id}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-white/60 font-mono">{r.name}</span>
                    <span className="font-mono" style={{ color: r.color }}>${fmtNum(pps)}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${(pps / 5000000) * 100}%`, background: `linear-gradient(90deg, ${r.color}88, ${r.color})`, boxShadow: `0 0 6px ${r.color}66` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-xl p-5" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
          <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-4">Coverage Distribution</div>
          <div className="space-y-2">
            {regions.map(r => (
              <div key={r.id}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-white/60 font-mono">{r.name}</span>
                  <span className="font-mono" style={{ color: r.color }}>{r.coverage.toFixed(1)}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${r.coverage}%`, background: `linear-gradient(90deg, ${r.color}66, ${r.color})` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
