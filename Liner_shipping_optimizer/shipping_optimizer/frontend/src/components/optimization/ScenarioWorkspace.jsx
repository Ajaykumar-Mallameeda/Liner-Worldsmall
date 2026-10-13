import { useState } from 'react';
import { fmt, fmtNum } from '../../utils/formatters.js';

export default function ScenarioWorkspace({ optimizationState }) {
  const [scenarioName, setScenarioName] = useState('');
  const [scenarioNotes, setScenarioNotes] = useState('');
  const [savedRuns, setSavedRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);

  const currentSnapshot = {
    id: Date.now(),
    name: scenarioName || `Run ${new Date().toISOString().slice(0, 10)}`,
    timestamp: new Date().toISOString(),
    profit: optimizationState.global.weeklyProfit,
    coverage: optimizationState.global.coverage,
    services: optimizationState.global.totalServices,
    runtime: optimizationState.global.runtime,
    margin: optimizationState.global.margin,
    iterations: optimizationState.iterations.length,
  };

  const handleSave = () => {
    if (!scenarioName.trim()) {
      setScenarioName(currentSnapshot.name);
    }
    setSavedRuns(prev => [currentSnapshot, ...prev].slice(0, 20));
    setSelectedRun(currentSnapshot.id);
    setScenarioName('');
    setScenarioNotes('');
  };

  const handleCompare = () => {
    setSelectedRun(null);
  };

  return (
    <div className="flex gap-4 h-full">
      {/* Saved runs panel */}
      <div className="w-72 flex-shrink-0 space-y-3">
        <div className="rounded-xl p-4" style={{ background: "rgba(0,212,255,0.04)", border: "1px solid rgba(0,212,255,0.2)" }}>
          <div className="text-xs font-mono text-cyan-400 uppercase tracking-widest mb-3">Save Current Run</div>
          <input type="text" placeholder="Scenario name"
            value={scenarioName} onChange={e => setScenarioName(e.target.value)}
            className="w-full px-2 py-1.5 rounded text-[10px] font-mono bg-white/5 border border-white/10 text-white/80 placeholder-white/30 mb-2 focus:outline-none focus:border-cyan-400/50"
            aria-label="Scenario name" />
          <textarea placeholder="Notes (optional)"
            value={scenarioNotes} onChange={e => setScenarioNotes(e.target.value)} rows={2}
            className="w-full px-2 py-1.5 rounded text-[10px] font-mono bg-white/5 border border-white/10 text-white/80 placeholder-white/30 mb-2 focus:outline-none focus:border-cyan-400/50"
            aria-label="Scenario notes" />
          <button onClick={handleSave}
            className="w-full py-1.5 rounded text-[10px] font-mono font-bold transition-all hover:scale-[1.02]"
            style={{ background: "rgba(0,212,255,0.15)", color: "#00d4ff", border: "1px solid rgba(0,212,255,0.3)" }}>
            💾 Save Current Run
          </button>
        </div>

        {savedRuns.length > 0 && (
          <div>
            <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest mb-2">Saved Runs</div>
            <div className="space-y-1">
              {savedRuns.map(run => (
                <button key={run.id} onClick={() => setSelectedRun(selectedRun === run.id ? null : run.id)}
                  className="w-full text-left px-3 py-2 rounded-lg transition-all"
                  style={{
                    background: selectedRun === run.id ? 'rgba(0,212,255,0.08)' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${selectedRun === run.id ? 'rgba(0,212,255,0.2)' : 'rgba(255,255,255,0.06)'}`,
                  }}>
                  <div className="text-[10px] font-mono text-white/80 font-bold">{run.name}</div>
                  <div className="text-[8px] text-white/30 font-mono">{run.timestamp.slice(0, 10)}</div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Main workspace */}
      <div className="flex-1 space-y-4">
        {savedRuns.length === 0 ? (
          <div className="rounded-xl p-8 text-center" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
            <div className="text-3xl mb-3 opacity-20">📋</div>
            <div className="text-sm text-white/50 font-mono">Scenario Workspace</div>
            <div className="text-xs text-white/30 font-mono mt-2 max-w-md mx-auto leading-relaxed">
              Save optimization runs to compare performance across scenarios.
              Name your run and click "Save Current Run" to begin building your comparison set.
            </div>
            <div className="text-[10px] text-white/20 font-mono mt-3">Future V2: Multi-run comparison, scenario import/export, weight configuration</div>
          </div>
        ) : selectedRun ? (
          <div className="rounded-xl p-5" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
            <div className="text-xs font-mono text-cyan-400 uppercase tracking-widest mb-4">Run Detail</div>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: 'Name', value: currentSnapshot.name, color: '#00d4ff' },
                { label: 'Date', value: currentSnapshot.timestamp.slice(0, 19).replace('T', ' '), color: '#888' },
                { label: 'Weekly Profit', value: fmt(currentSnapshot.profit), color: '#10b981' },
                { label: 'Coverage', value: `${currentSnapshot.coverage.toFixed(1)}%`, color: '#00d4ff' },
                { label: 'Services', value: fmtNum(currentSnapshot.services), color: '#8b5cf6' },
                { label: 'Runtime', value: `${currentSnapshot.runtime}s`, color: '#f59e0b' },
                { label: 'Margin', value: `${currentSnapshot.margin.toFixed(1)}%`, color: '#ec4899' },
                { label: 'Iterations', value: currentSnapshot.iterations.toString(), color: '#6366f1' },
              ].map(({ label, value, color }) => (
                <div key={label} className="rounded-lg p-3" style={{ background: `${color}08`, border: `1px solid ${color}22` }}>
                  <div className="text-[9px] text-white/40 font-mono">{label}</div>
                  <div className="text-sm font-bold font-mono mt-0.5" style={{ color }}>{value}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-white/5 flex gap-2">
              <button onClick={handleCompare} className="text-[10px] px-3 py-1 rounded font-mono bg-white/5 text-white/50 hover:text-white/80">Close Detail</button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-white/30 font-mono italic text-xs">Select a saved run to view details</div>
          </div>
        )}

        {/* Future V2 placeholder */}
        <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.015)", border: "1px solid rgba(255,255,255,0.04)" }}>
          <div className="text-[9px] font-mono text-white/20 uppercase tracking-widest">V2 Roadmap</div>
          <div className="text-[9px] text-white/20 font-mono mt-1">
            Compare Mode · Scenario Import/Export · Weight Presets · Constraint Configuration · Batch Optimization
          </div>
        </div>
      </div>
    </div>
  );
}
