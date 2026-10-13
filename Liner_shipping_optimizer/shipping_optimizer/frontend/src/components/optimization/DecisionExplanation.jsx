import { useMemo } from 'react';

export default function DecisionExplanation({ optimizationState }) {
  const decision = useMemo(() => {
    const do_ = optimizationState.global.decision_output || {};
    const fb = do_.feedback || {};
    const ev = do_.evaluation || {};
    return { feedback: fb, evaluation: ev };
  }, [optimizationState.global.decision_output]);

  const { feedback, evaluation } = decision;

  if (!feedback || Object.keys(feedback).length === 0) {
    return (
      <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-2">Decision Explanation</div>
        <div className="text-xs text-white/40 font-mono italic">Not Available</div>
      </div>
    );
  }

  const weights = feedback.weight_adjustments || {};
  const hasWeights = Object.keys(weights).length > 0;

  return (
    <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-3">Decision Explanation</div>

      {/* Evaluation summary */}
      {evaluation.score != null && (
        <div className="mb-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] text-white/40 font-mono">Coordinator Score</span>
            <span className="text-sm font-mono font-bold text-cyan-400">{evaluation.score}/{evaluation.max}</span>
            <span className="text-[10px] text-white/30 font-mono">({evaluation.status})</span>
          </div>
          {(evaluation.reasons || []).length > 0 && (
            <div className="space-y-0.5">
              {evaluation.reasons.map((r, i) => (
                <div key={i} className="text-[10px] text-white/50 font-mono leading-relaxed">• {r}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Weight allocation */}
      {hasWeights && (
        <div className="mb-3">
          <div className="text-[10px] text-white/40 font-mono mb-2">Weight Allocation</div>
          <div className="space-y-1.5">
            {[
              { key: 'profit_weight', label: 'Profit', color: '#00d4ff' },
              { key: 'coverage_weight', label: 'Coverage', color: '#10b981' },
              { key: 'cost_weight', label: 'Cost', color: '#f59e0b' },
            ].map(({ key, label, color }) => {
              const val = weights[key];
              if (val == null) return null;
              return (
                <div key={key}>
                  <div className="flex justify-between text-[10px] mb-0.5">
                    <span className="text-white/60 font-mono">{label}</span>
                    <span className="text-white/80 font-mono">{(val * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${val * 100}%`, background: `linear-gradient(90deg, ${color}66, ${color})` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Feedback status */}
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: "Convergence Score", value: feedback.convergence_score?.toFixed(3), color: "#10b981" },
          { label: "Coverage Gap", value: feedback.coverage_gap != null ? `${feedback.coverage_gap.toFixed(2)}pp` : null, color: "#f59e0b" },
          { label: "Iteration", value: feedback.iteration != null ? `${feedback.iteration}` : null, color: "#00d4ff" },
          { label: "At Iteration Cap", value: feedback.at_iteration_cap ? "Yes" : "No", color: feedback.at_iteration_cap ? "#ef4444" : "#10b981" },
        ].filter(item => item.value != null).map(({ label, value, color }) => (
          <div key={label} className="rounded p-1.5 text-center" style={{ background: `${color}08`, border: `1px solid ${color}22` }}>
            <div className="text-[11px] font-mono font-bold" style={{ color }}>{value}</div>
            <div className="text-[8px] text-white/40 font-mono uppercase tracking-wider">{label}</div>
          </div>
        ))}
      </div>

      {/* Reason if present */}
      {feedback.rerun_reason && (
        <div className="mt-2 pt-2 border-t border-white/5">
          <div className="text-[9px] text-white/30 font-mono leading-relaxed">{feedback.rerun_reason}</div>
        </div>
      )}
    </div>
  );
}
