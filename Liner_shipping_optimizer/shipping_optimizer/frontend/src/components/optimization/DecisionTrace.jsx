import { useMemo, useState } from 'react';

const STAGES = [
  { id: 'coordinator', label: 'Coordinator Agent', desc: 'LLM evaluation + conflict detection' },
  { id: 'regional', label: 'Regional Agents', desc: '5 parallel GA + MILP solvers' },
  { id: 'consensus', label: 'Consensus Engine', desc: 'Weight reconciliation + archetype voting' },
  { id: 'ga', label: 'Genetic Algorithm', desc: 'Service generation + frequency optimization' },
  { id: 'milp', label: 'MILP Optimizer', desc: 'Flow optimization + final selection' },
  { id: 'final', label: 'Final Network', desc: 'Constraint validation + certification' },
];

export default function DecisionTrace({ optimizationState }) {
  const [activeStage, setActiveStage] = useState(null);

  const metrics = useMemo(() => {
    const do_ = optimizationState.global.decision_output || {};
    const fb = do_.feedback || {};
    const ev = do_.evaluation || {};
    return {
      iteration: fb.iteration ?? optimizationState.iterations.length,
      convergenceScore: fb.convergence_score,
      coverageGap: fb.coverage_gap,
      conflictCount: fb.conflict_count ?? 0,
      weightProfit: fb.weight_adjustments?.profit_weight,
      weightCoverage: fb.weight_adjustments?.coverage_weight,
      weightCost: fb.weight_adjustments?.cost_weight,
      status: ev.status,
      evaluationScore: ev.score,
      evaluationMax: ev.max,
      reasons: ev.reasons || [],
    };
  }, [optimizationState]);

  const stageStatus = useMemo(() => {
    const done = !optimizationState.isPipelineRunning;
    return {
      coordinator: done ? 'complete' : (optimizationState.currentStage === 'Coordinator' ? 'running' : 'pending'),
      regional: done ? 'complete' : 'pending',
      consensus: done ? 'complete' : 'pending',
      ga: done ? 'complete' : 'pending',
      milp: done ? 'complete' : 'pending',
      final: done ? 'complete' : 'pending',
    };
  }, [optimizationState.isPipelineRunning, optimizationState.currentStage]);

  return (
    <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-3">AI Decision Trace</div>

      <div className="flex flex-col gap-1">
        {STAGES.map((stage, i) => {
          const status = stageStatus[stage.id];
          const isActive = activeStage === stage.id;
          const statusColor = status === 'complete' ? '#10b981' : status === 'running' ? '#f59e0b' : 'rgba(255,255,255,0.15)';
          const statusIcon = status === 'complete' ? '✓' : status === 'running' ? '○' : '·';

          return (
            <div key={stage.id}>
              <div
                onClick={() => setActiveStage(isActive ? null : stage.id)}
                className="flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-all duration-150"
                style={{ background: isActive ? 'rgba(0,212,255,0.08)' : 'transparent', border: `1px solid ${isActive ? 'rgba(0,212,255,0.2)' : 'transparent'}` }}
              >
                <div className="flex flex-col items-center gap-0.5">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: statusColor }} />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono" style={{ color: status === 'complete' ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.5)' }}>
                      {stage.label}
                    </span>
                    <span className="text-[10px] font-mono" style={{ color: statusColor }}>{statusIcon}</span>
                  </div>
                  <div className="text-[9px] text-white/30 font-mono">{stage.desc}</div>
                </div>
              </div>

              {isActive && stage.id === 'coordinator' && metrics.reasons.length > 0 && (
                <div className="ml-6 mb-1 px-3 py-2 rounded-lg" style={{ background: "rgba(255,255,255,0.03)" }}>
                  <div className="text-[10px] text-white/40 font-mono mb-1">Coordinator Feedback</div>
                  <div className="text-[10px] text-white/60 font-mono leading-relaxed">
                    {metrics.reasons.map((r, i) => <div key={i}>• {r}</div>)}
                  </div>
                  {metrics.weightProfit != null && (
                    <div className="mt-1 text-[9px] text-white/40 font-mono">
                      Weights: profit {metrics.weightProfit.toFixed(3)} · coverage {metrics.weightCoverage.toFixed(3)} · cost {metrics.weightCost.toFixed(3)}
                    </div>
                  )}
                </div>
              )}

              {isActive && stage.id === 'consensus' && (
                <div className="ml-6 mb-1 px-3 py-2 rounded-lg" style={{ background: "rgba(255,255,255,0.03)" }}>
                  <div className="text-[10px] text-white/40 font-mono mb-1">Convergence Score: {metrics.convergenceScore?.toFixed(3) ?? 'N/A'}</div>
                  <div className="text-[10px] text-white/60 font-mono">Coverage gap: {metrics.coverageGap != null ? `${metrics.coverageGap.toFixed(2)}pp` : 'N/A'} from 70% target</div>
                  <div className="text-[10px] text-white/60 font-mono">Conflicts detected: {metrics.conflictCount}</div>
                </div>
              )}

              {i < STAGES.length - 1 && (
                <div className="ml-[5px] pl-[1px] h-2">
                  <div className="w-px h-full" style={{ background: 'rgba(255,255,255,0.08)' }} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
