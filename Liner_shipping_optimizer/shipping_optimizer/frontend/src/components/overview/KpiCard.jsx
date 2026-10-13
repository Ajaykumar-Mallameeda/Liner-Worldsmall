import Sparkline from '../common/Sparkline.jsx';
import BenchmarkBadge from '../common/BenchmarkBadge.jsx';

export default function KpiCard({ label, value, sub, color, sparkData, benchmark, rawValue }) {
  return (
    <div className="rounded-xl p-5 transition-all duration-300 hover:scale-[1.02] cursor-default group"
      style={{ background: `${color}08`, border: `1px solid ${color}22`, boxShadow: `0 0 0 transparent`, transition: "box-shadow 0.3s" }}
      onMouseEnter={e => e.currentTarget.style.boxShadow = `0 0 30px ${color}20`}
      onMouseLeave={e => e.currentTarget.style.boxShadow = "0 0 0 transparent"}>
      <div className="flex items-start justify-between mb-3">
        <span className="text-xs font-mono text-white/40 uppercase tracking-widest">{label}</span>
        {sparkData && <Sparkline data={sparkData} color={color} />}
      </div>
      <div className="text-3xl font-bold font-mono tracking-tight" style={{ color, textShadow: `0 0 20px ${color}66` }}>
        {value}
        {benchmark && rawValue != null && <BenchmarkBadge value={rawValue} benchmark={benchmark} compact />}
      </div>
      {sub && <div className="text-xs text-white/40 mt-1 font-mono">{sub}</div>}
      <div className="mt-3 h-px w-full" style={{ background: `linear-gradient(90deg, ${color}44, transparent)` }} />
    </div>
  );
}
