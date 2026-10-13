import ProgressBar from '../common/ProgressBar.jsx';
import { fmt, fmtNum, parseStrategyCode } from '../../utils/formatters.js';

export default function RegionCard({ r, onClick, selected }) {
  return (
    <div
      onClick={() => onClick(r)}
      className="cursor-pointer rounded-xl p-4 transition-all duration-300 hover:scale-[1.02]"
      style={{
        background: selected ? `${r.color}12` : "rgba(255,255,255,0.025)",
        border: `1px solid ${selected ? r.color + "55" : "rgba(255,255,255,0.07)"}`,
        boxShadow: selected ? `0 0 30px ${r.color}20, inset 0 0 20px ${r.color}08` : "none"
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: r.color, boxShadow: `0 0 8px ${r.color}` }} />
          <span className="text-sm font-semibold text-white/90" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>{r.name}</span>
        </div>
        <span className="text-xs px-2 py-0.5 rounded font-mono" style={{ background: `${r.color}20`, color: r.color }}>{parseStrategyCode(r.strategy)}</span>
      </div>

      <div className="text-xl font-bold text-white mb-1" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
        {fmt(r.profit)}
      </div>
      <div className="text-xs text-white/40 mb-3">weekly profit</div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        {[
          { label: "Coverage", value: `${r.coverage.toFixed(1)}%` },
          { label: "Services", value: r.services },
          { label: "Margin", value: `${r.margin.toFixed(1)}%` },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg p-2" style={{ background: "rgba(255,255,255,0.04)" }}>
            <div className="text-xs text-white/40 mb-0.5">{label}</div>
            <div className="text-sm font-mono text-white/90">{value}</div>
          </div>
        ))}
      </div>

      <div className="mb-2">
        <div className="flex justify-between text-xs text-white/40 mb-1">
          <span>Coverage</span><span>{r.coverage.toFixed(1)}%</span>
        </div>
        <ProgressBar value={r.coverage} color={r.color} />
      </div>

      <div className="flex flex-wrap gap-1 mt-2">
        {r.hubs.slice(0, 3).map(h => (
          <span key={h} className="text-xs px-1.5 py-0.5 rounded font-mono" style={{ background: `${r.color}15`, color: r.color + "cc", border: `1px solid ${r.color}30` }}>
            {h}
          </span>
        ))}
        <span className="text-xs px-1.5 py-0.5 rounded font-mono text-white/30" style={{ background: "rgba(255,255,255,0.04)" }}>
          +{r.hubs.length - 3}
        </span>
      </div>
    </div>
  );
}
