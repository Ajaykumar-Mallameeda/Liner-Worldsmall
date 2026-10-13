export default function ConflictView({ optimizationState }) {
  const decision = optimizationState.global.decision_output || {};
  const conflicts = decision.conflicts || [];
  const evalData = decision.evaluation || { score: null, max: null, status: "No data", reasons: ["No evaluation data available"] };
  const conflictCount = conflicts.length;
  const severity = decision.feedback?.conflict_severity || 0;

  const hasConflicts = conflictCount > 0;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Conflicts Detected", value: conflictCount.toString(), color: hasConflicts ? "#ef4444" : "#10b981", icon: hasConflicts ? "⚠" : "✓" },
          { label: "Conflicts Resolved", value: decision.resolution_log?.length.toString() || "0", color: "#10b981", icon: "✓" },
          { label: "Conflict Severity", value: severity > 0 ? severity.toString() : "None", color: severity > 0 ? "#ef4444" : "#10b981", icon: "○" },
          { label: "Evaluation Status", value: evalData.status || "No data", color: "#f59e0b", icon: "◎" },
        ].map(({ label, value, color, icon }) => (
          <div key={label} className="rounded-xl p-4 text-center" style={{ background: `${color}08`, border: `1px solid ${color}22` }}>
            <div className="text-2xl mb-1" style={{ color }}>{icon}</div>
            <div className="text-xl font-bold font-mono" style={{ color }}>{value}</div>
            <div className="text-xs text-white/40 mt-1 font-mono">{label}</div>
          </div>
        ))}
      </div>

      <div className="rounded-xl p-5" style={{ background: hasConflicts ? "rgba(239,68,68,0.05)" : "rgba(16,185,129,0.05)", border: `1px solid ${hasConflicts ? "rgba(239,68,68,0.2)" : "rgba(16,185,129,0.2)"}` }}>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: hasConflicts ? "#ef4444" : "#10b981", boxShadow: `0 0 8px ${hasConflicts ? "#ef4444" : "#10b981"}` }} />
          <span className="text-sm font-mono" style={{ color: hasConflicts ? "#ef4444" : "#10b981" }}>
            {hasConflicts ? `${conflictCount} Regional Conflicts Detected` : "No Regional Conflicts Detected"}
          </span>
        </div>
        <p className="text-xs text-white/50 font-mono leading-relaxed">
          {hasConflicts
            ? "The CoordinatorAgent detected overlapping service assignments or resource bottlenecks across regions. Resolution protocols are active."
            : "The CoordinatorAgent found zero overlapping service assignments across all regional agents. Each service ID is uniquely assigned to exactly one region. Resolution protocol was not triggered."}
        </p>
      </div>

      <div className="rounded-xl p-5" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-4">Coordinator Evaluation</div>
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Score", value: evalData.score != null ? `${evalData.score} / ${evalData.max}` : "—", color: "#f59e0b" },
            { label: "Status", value: evalData.status || "No data", color: "#f59e0b" },
            { label: "Reasons", value: evalData.reasons?.length > 0 ? evalData.reasons[0].slice(0,25)+"..." : "N/A", color: "#f59e0b" },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-lg p-3" style={{ background: "rgba(255,255,255,0.04)" }}>
              <div className="text-xs text-white/40 font-mono mb-1">{label}</div>
              <div className="text-sm font-mono" style={{ color }} title={label==="Reasons" ? evalData.reasons?.join(", ") : undefined}>{value}</div>
            </div>
          ))}
        </div>
        <div className="mt-4 text-xs text-white/40 font-mono leading-relaxed">
          {evalData.reasons?.join(". ") || "System achieved strong profitability but demand coverage requires further balancing in the next planning cycle."}
        </div>
      </div>
    </div>
  );
}
