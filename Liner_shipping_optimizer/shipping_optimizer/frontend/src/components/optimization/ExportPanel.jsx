import { useMemo, useCallback } from 'react';

export default function ExportPanel({ optimizationState }) {
  const services = useMemo(() => optimizationState.global.selected_services || [], [optimizationState.global.selected_services]);
  const regions = useMemo(() => Object.values(optimizationState.regions), [optimizationState.regions]);
  const decision = optimizationState.global.decision_output || {};
  const tc = optimizationState.global.test_scorecard || {};

  const exportJSON = useCallback(() => {
    const data = {
      exported: new Date().toISOString(),
      summary: {
        weeklyProfit: optimizationState.global.weeklyProfit,
        annualProfit: optimizationState.global.annualProfit,
        coverage: optimizationState.global.coverage,
        totalServices: optimizationState.global.totalServices,
        runtime: optimizationState.global.runtime,
        margin: optimizationState.global.margin,
      },
      regions: regions.map(r => ({
        name: r.name,
        profit: r.profit,
        coverage: r.coverage,
        services: r.services,
        margin: r.margin,
        generated: r.generated,
        filtered: r.filtered,
        selected: r.selected,
        hubs: r.hubs,
      })),
      testScorecard: tc,
      iterationAudit: optimizationState.iterations,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `optimization-export-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [optimizationState, regions, tc]);

  const exportCSV = useCallback(() => {
    if (!services.length) return;
    const headers = ['ID','Ports','Load','Capacity','VesselClass','WeeklyProfit','Margin','Region'];
    const rows = services.map(s => [
      s.id, (s.ports || []).join(';'), s.load, s.capacity, s.vessel_class,
      (s.weekly_profit || 0).toFixed(2), (s.margin_pct || 0).toFixed(2), s.region
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `routes-export-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [services]);

  const exportRegionalCSV = useCallback(() => {
    if (!regions.length) return;
    const headers = ['Region','Profit','Coverage','Services','Margin','Generated','Filtered','Selected'];
    const rows = regions.map(r => [r.name, r.profit, r.coverage, r.services, r.margin, r.generated, r.filtered, r.selected]);
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `regions-export-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [regions]);

  return (
    <div className="space-y-5">
      <div className="rounded-xl p-5" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-4">Export Center</div>
        <div className="grid grid-cols-2 gap-4">
          <button onClick={exportJSON} className="rounded-xl p-5 text-left transition-all hover:scale-[1.01]" style={{ background: "rgba(0,212,255,0.06)", border: "1px solid rgba(0,212,255,0.2)" }}>
            <div className="text-lg mb-1">📄</div>
            <div className="text-sm font-mono font-bold text-cyan-400">Export JSON</div>
            <div className="text-[10px] text-white/40 font-mono mt-1">Complete optimization data · Metrics · Regions · Services</div>
          </button>
          <button onClick={exportCSV} className="rounded-xl p-5 text-left transition-all hover:scale-[1.01]" style={{ background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.2)" }}>
            <div className="text-lg mb-1">📊</div>
            <div className="text-sm font-mono font-bold text-emerald-400">Export Routes CSV</div>
            <div className="text-[10px] text-white/40 font-mono mt-1">{services.length} services · Sortable spreadsheet format</div>
          </button>
          <button onClick={exportRegionalCSV} className="rounded-xl p-5 text-left transition-all hover:scale-[1.01]" style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)" }}>
            <div className="text-lg mb-1">🌍</div>
            <div className="text-sm font-mono font-bold text-amber-400">Export Regions CSV</div>
            <div className="text-[10px] text-white/40 font-mono mt-1">{regions.length} regions · KPIs per region</div>
          </button>
          <button disabled className="rounded-xl p-5 text-left opacity-40" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <div className="text-lg mb-1">📑</div>
            <div className="text-sm font-mono font-bold text-white/50">Export PDF Summary</div>
            <div className="text-[10px] text-white/30 font-mono mt-1">Available in V2 · Executive-ready PDF reports</div>
          </button>
        </div>
      </div>

      {/* Export preview */}
      <div className="rounded-xl p-5" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-4">Export Preview</div>
        <div className="grid grid-cols-2 gap-4 text-[11px] font-mono">
          <div>
            <div className="text-white/30 uppercase tracking-wider text-[9px] mb-2">Metrics Snapshot</div>
            {[
              ['Weekly Profit', optimizationState.global.weeklyProfit],
              ['Coverage', `${optimizationState.global.coverage.toFixed(1)}%`],
              ['Services', optimizationState.global.totalServices],
              ['Runtime', `${optimizationState.global.runtime}s`],
              ['Margin', `${optimizationState.global.margin.toFixed(1)}%`],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between py-0.5 border-b border-white/5">
                <span className="text-white/40">{k}</span><span className="text-white/70">{v}</span>
              </div>
            ))}
          </div>
          <div>
            <div className="text-white/30 uppercase tracking-wider text-[9px] mb-2">File Summary</div>
            <div className="text-white/50 leading-relaxed">
              <div>Routes: {services.length}</div>
              <div>Regions: {regions.length}</div>
              <div>Date: {new Date().toISOString().slice(0, 10)}</div>
              <div>Formats: JSON, CSV (×2)</div>
              <div className="mt-2 text-[9px] text-white/30">Click any export button above to download</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
