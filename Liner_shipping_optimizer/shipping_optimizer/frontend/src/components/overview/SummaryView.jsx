import { fmt, fmtNum } from '../../utils/formatters.js';

export default function SummaryView({ optimizationState }) {
  const summaryText = optimizationState.global.executive_summary || "";

  const extractSection = (header) => {
    const lines = summaryText.split('\n');
    let inSection = false;
    const items = [];
    for (const line of lines) {
      if (line.startsWith(header)) {
        inSection = true;
        continue;
      }
      if (inSection) {
        if (line.trim() === "" || (!line.startsWith("-") && !line.startsWith(" "))) break;
        if (line.startsWith("-")) items.push(line.replace("-", "").trim());
      }
    }
    return items;
  };

  const strengths = extractSection("Strengths:");
  const weaknesses = extractSection("Weaknesses:");
  const actions = extractSection("Priority Actions:");
  const isGood = summaryText.includes("Verdict: Good");

  return (
    <div className="space-y-5">
      <div className="rounded-xl p-6" style={{ background: "linear-gradient(135deg, rgba(16,185,129,0.08), rgba(0,212,255,0.08))", border: "1px solid rgba(16,185,129,0.2)" }}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: isGood ? "#10b981" : "#f59e0b", boxShadow: `0 0 12px ${isGood ? "#10b981" : "#f59e0b"}` }} />
          <span className="text-sm font-mono font-semibold uppercase tracking-widest" style={{ color: isGood ? "#10b981" : "#f59e0b" }}>
            {isGood ? "Verdict: Good" : "Verdict: Needs Improvement"}
          </span>
        </div>
        <p className="text-base text-white/80 font-mono leading-relaxed">
          The global weekly profit is <span className="text-emerald-400 font-bold">{fmt(optimizationState.global.weeklyProfit)}</span>, indicating strong financial performance
          with an <span className="text-emerald-400 font-bold">{optimizationState.global.margin?.toFixed(1)}% profit margin</span> across {fmtNum(optimizationState.global.totalServices)} deployed services.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl p-5" style={{ background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.2)" }}>
          <div className="text-xs font-mono text-emerald-400 uppercase tracking-widest mb-3">Strengths</div>
          {(strengths.length > 0 ? strengths : [
            "Data unavailable for this run.",
            "Data unavailable for this run.",
            "Data unavailable for this run."
          ]).map((s, i) => (
            <div key={i} className="flex gap-2 mb-2">
              <span className="text-emerald-400 text-xs mt-0.5 flex-shrink-0">+</span>
              <span className="text-xs text-white/60 font-mono leading-relaxed">{s}</span>
            </div>
          ))}
        </div>

        <div className="rounded-xl p-5" style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)" }}>
          <div className="text-xs font-mono text-red-400 uppercase tracking-widest mb-3">Weaknesses</div>
          {(weaknesses.length > 0 ? weaknesses : [
            "Data unavailable for this run.",
            "Data unavailable for this run."
          ]).map((s, i) => (
            <div key={i} className="flex gap-2 mb-2">
              <span className="text-red-400 text-xs mt-0.5 flex-shrink-0">−</span>
              <span className="text-xs text-white/60 font-mono leading-relaxed">{s}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl p-5" style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)" }}>
        <div className="text-xs font-mono text-amber-400 uppercase tracking-widest mb-3">Priority Actions</div>
        <div className="grid grid-cols-2 gap-3">
          {(actions.length > 0 ? actions : [
            "Data unavailable for this run.",
            "Data unavailable for this run.",
            "Data unavailable for this run."
          ]).map((detail, i) => (
            <div key={i} className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.03)" }}>
              <div className="text-xs font-mono text-amber-400 mb-1">{String(i + 1).padStart(2, "0")} · Action</div>
              <div className="text-xs text-white/50 font-mono leading-relaxed">{detail}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
