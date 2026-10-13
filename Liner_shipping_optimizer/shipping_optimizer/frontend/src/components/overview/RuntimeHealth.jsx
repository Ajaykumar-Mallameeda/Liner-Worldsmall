import PulseDot from '../common/PulseDot.jsx';

export default function RuntimeHealth({ optimizationState }) {
  const sc = optimizationState.global.test_scorecard || {};
  const llm = optimizationState.global.llm_runtime_metrics || {};
  const passed = sc.assertions_passed;
  const total = sc.assertions_total;
  const score = sc.score;
  const warnings = sc.warnings;

  return (
    <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-3">Runtime Health</div>

      <div className="grid grid-cols-2 gap-2 mb-3">
        {/* Connection status */}
        <div className="rounded-lg p-2 flex items-center gap-2" style={{ background: "rgba(255,255,255,0.03)" }}>
          <PulseDot color={optimizationState.isConnected ? "#10b981" : "#ef4444"} />
          <div>
            <div className="text-[10px] font-mono" style={{ color: optimizationState.isConnected ? "#10b981" : "#ef4444" }}>
              {optimizationState.isConnected ? "Connected" : "Disconnected"}
            </div>
            <div className="text-[8px] text-white/30 font-mono">WebSocket</div>
          </div>
        </div>

        {/* Pipeline status */}
        <div className="rounded-lg p-2 flex items-center gap-2" style={{ background: "rgba(255,255,255,0.03)" }}>
          <PulseDot color={optimizationState.isPipelineRunning ? "#f59e0b" : "#10b981"} />
          <div>
            <div className="text-[10px] font-mono text-white/80">
              {optimizationState.isPipelineRunning ? (optimizationState.currentStage || "Running") : "Complete"}
            </div>
            <div className="text-[8px] text-white/30 font-mono">Pipeline</div>
          </div>
        </div>
      </div>

      {/* Test scorecard */}
      {passed != null && (
        <div className="mb-2">
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-1.5">Backend Certification</div>
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded p-1.5 text-center" style={{ background: "rgba(16,185,129,0.08)" }}>
              <div className="text-xs font-mono font-bold text-emerald-400">{passed}/{total}</div>
              <div className="text-[8px] text-white/40 font-mono">Assertions</div>
            </div>
            <div className="rounded p-1.5 text-center" style={{ background: "rgba(0,212,255,0.08)" }}>
              <div className="text-xs font-mono font-bold text-cyan-400">{score != null ? `${score}%` : "—"}</div>
              <div className="text-[8px] text-white/40 font-mono">Score</div>
            </div>
            <div className="rounded p-1.5 text-center" style={{ background: (warnings || 0) > 0 ? "rgba(245,158,11,0.08)" : "rgba(16,185,129,0.08)" }}>
              <div className="text-xs font-mono font-bold" style={{ color: (warnings || 0) > 0 ? "#f59e0b" : "#10b981" }}>{warnings || 0}</div>
              <div className="text-[8px] text-white/40 font-mono">Warnings</div>
            </div>
          </div>
        </div>
      )}

      {/* LLM runtime metrics */}
      {Object.keys(llm).length > 0 && (
        <div>
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-1.5">AI Activity</div>
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded p-1.5 text-center" style={{ background: "rgba(139,92,246,0.08)" }}>
              <div className="text-xs font-mono font-bold text-violet-400">{llm.llm_calls ?? 0}</div>
              <div className="text-[8px] text-white/40 font-mono">LLM Calls</div>
            </div>
            <div className="rounded p-1.5 text-center" style={{ background: "rgba(139,92,246,0.08)" }}>
              <div className="text-xs font-mono font-bold text-violet-400">{llm.coordinator_llm_calls ?? 0}</div>
              <div className="text-[8px] text-white/40 font-mono">Coordinator Calls</div>
            </div>
            <div className="rounded p-1.5 text-center" style={{ background: "rgba(16,185,129,0.08)" }}>
              <div className="text-xs font-mono font-bold text-emerald-400">{llm.coordinator_fallback_count ?? 0}</div>
              <div className="text-[8px] text-white/40 font-mono">Fallbacks</div>
            </div>
          </div>
          {llm.coordinator_ai_generated && (
            <div className="mt-1 text-[9px] text-violet-400/60 font-mono">✓ AI-generated decisions active</div>
          )}
          {llm.servicegen_regions > 0 && (
            <div className="text-[9px] text-white/30 font-mono">
              {llm.servicegen_regions} service generator regions · {llm.servicegen_ai_count} AI generated · {llm.servicegen_fallback_count} fallback
            </div>
          )}
        </div>
      )}
    </div>
  );
}
