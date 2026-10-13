import { useMemo } from 'react';
import { computeRegionalInsights } from '../../utils/fleetStats.js';
import { fmt, fmtNum } from '../../utils/formatters.js';

export default function OptimizationInsights({ optimizationState }) {
  const insights = useMemo(
    () => computeRegionalInsights(Object.values(optimizationState.regions)),
    [optimizationState.regions]
  );

  const regions = Object.values(optimizationState.regions);
  if (regions.length === 0) {
    return (
      <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-2">Optimization Insights</div>
        <div className="text-xs text-white/40 font-mono italic">Not Available</div>
      </div>
    );
  }

  const highlights = [
    insights.bestProfit && { label: "Best Profit", region: insights.bestProfit.name, value: fmt(insights.bestProfit.profit), color: "#10b981" },
    insights.worstProfit && { label: "Lowest Profit", region: insights.worstProfit.name, value: fmt(insights.worstProfit.profit), color: "#ef4444" },
    insights.bestCoverage && { label: "Highest Coverage", region: insights.bestCoverage.name, value: `${insights.bestCoverage.coverage.toFixed(1)}%`, color: "#00d4ff" },
    insights.worstCoverage && { label: "Lowest Coverage", region: insights.worstCoverage.name, value: `${insights.worstCoverage.coverage.toFixed(1)}%`, color: "#f59e0b" },
    insights.mostServices && { label: "Most Services", region: insights.mostServices.name, value: fmtNum(insights.mostServices.services), color: "#8b5cf6" },
    insights.bestMargin && { label: "Best Margin", region: insights.bestMargin.name, value: `${insights.bestMargin.margin.toFixed(1)}%`, color: "#ec4899" },
  ].filter(Boolean);

  const avgCoverage = regions.length > 0 ? (regions.reduce((s, r) => s + (r.coverage || 0), 0) / regions.length).toFixed(1) : 0;
  const totalProfit = insights.totalProfit;

  return (
    <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-3">Optimization Insights</div>

      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="rounded-lg p-2 text-center" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)" }}>
          <div className="text-lg font-bold font-mono text-emerald-400">{fmt(totalProfit)}</div>
          <div className="text-[9px] text-white/40 font-mono">Total Weekly Profit</div>
        </div>
        <div className="rounded-lg p-2 text-center" style={{ background: "rgba(0,212,255,0.08)", border: "1px solid rgba(0,212,255,0.2)" }}>
          <div className="text-lg font-bold font-mono text-cyan-400">{avgCoverage}%</div>
          <div className="text-[9px] text-white/40 font-mono">Avg Regional Coverage</div>
        </div>
      </div>

      <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-2">Regional Rankings</div>
      <div className="space-y-1.5">
        {highlights.map((h, i) => (
          <div key={i} className="flex items-center justify-between px-2 py-1.5 rounded-lg" style={{ background: "rgba(255,255,255,0.03)" }}>
            <div className="flex items-center gap-2">
              <div className="w-1 h-1 rounded-full" style={{ backgroundColor: h.color }} />
              <span className="text-[10px] text-white/50 font-mono">{h.label}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-white/30 font-mono">{h.region}</span>
              <span className="text-[11px] font-mono font-bold" style={{ color: h.color }}>{h.value}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
