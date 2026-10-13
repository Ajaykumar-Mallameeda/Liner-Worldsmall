import { useMemo, useState } from 'react';
import { fmt, fmtNum } from '../../utils/formatters.js';

export default function FleetDashboard({ optimizationState }) {
  const [sortKey, setSortKey] = useState('count');
  const [sortDir, setSortDir] = useState('desc');
  const [classFilter, setClassFilter] = useState('all');
  const [regionFilter, setRegionFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  const fleet = useMemo(() => {
    const svcs = optimizationState.global.selected_services || [];
    if (!svcs.length) return { vessels: [], classes: {}, byRegion: {}, total: 0 };

    const classes = {};
    const byRegion = {};
    svcs.forEach(s => {
      const cls = s.vessel_class || 'Unknown';
      const reg = s.region || 'Unknown';
      if (!classes[cls]) classes[cls] = { count: 0, totalCap: 0, totalLoad: 0, totalProfit: 0 };
      classes[cls].count++;
      classes[cls].totalCap += s.capacity || 0;
      classes[cls].totalLoad += s.load || 0;
      classes[cls].totalProfit += s.weekly_profit || 0;
      if (!byRegion[reg]) byRegion[reg] = { count: 0, totalCap: 0, totalLoad: 0 };
      byRegion[reg].count++;
      byRegion[reg].totalCap += s.capacity || 0;
      byRegion[reg].totalLoad += s.load || 0;
    });

    return { classes, byRegion, total: svcs.length, vessels: svcs };
  }, [optimizationState.global.selected_services]);

  const filteredVessels = useMemo(() => {
    let list = fleet.vessels;
    if (classFilter !== 'all') list = list.filter(s => s.vessel_class === classFilter);
    if (regionFilter !== 'all') list = list.filter(s => s.region === regionFilter);
    if (searchTerm) {
      const t = searchTerm.toLowerCase();
      list = list.filter(s => s.id?.toLowerCase().includes(t) || s.ports?.some(p => p.toLowerCase().includes(t)));
    }
    list = [...list].sort((a, b) => {
      const av = sortKey === 'profit' ? (a.weekly_profit || 0) : sortKey === 'load' ? (a.load || 0) : sortKey === 'capacity' ? (a.capacity || 0) : sortKey === 'util' ? ((a.load || 0) / (a.capacity || 1)) : 0;
      const bv = sortKey === 'profit' ? (b.weekly_profit || 0) : sortKey === 'load' ? (b.load || 0) : sortKey === 'capacity' ? (b.capacity || 0) : sortKey === 'util' ? ((b.load || 0) / (b.capacity || 1)) : 0;
      return sortDir === 'asc' ? av - bv : bv - av;
    });
    return list;
  }, [fleet.vessels, classFilter, regionFilter, searchTerm, sortKey, sortDir]);

  if (!fleet.total) {
    return <div className="text-white/40 font-mono italic text-center py-8">Fleet data not available</div>;
  }

  const classes = Object.entries(fleet.classes).sort((a, b) => b[1].count - a[1].count);

  const SortHeader = ({ k, label }) => (
    <th className="text-left px-2 py-1.5 text-[10px] font-mono text-white/40 uppercase tracking-wider cursor-pointer select-none"
      onClick={() => { if (sortKey === k) setSortDir(d => d === 'asc' ? 'desc' : 'asc'); else { setSortKey(k); setSortDir('desc'); } }}>
      {label} {sortKey === k ? (sortDir === 'asc' ? '▲' : '▼') : ''}
    </th>
  );

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Vessels', value: fmtNum(fleet.total), color: '#00d4ff' },
          { label: 'Vessel Classes', value: classes.length.toString(), color: '#8b5cf6' },
          { label: 'Total Capacity', value: `${(Object.values(fleet.classes).reduce((s,c) => s + c.totalCap, 0) / 1000).toFixed(0)}K TEU`, color: '#10b981' },
          { label: 'Regions Served', value: Object.keys(fleet.byRegion).length.toString(), color: '#f59e0b' },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-xl p-4 text-center" style={{ background: `${color}08`, border: `1px solid ${color}22` }}>
            <div className="text-2xl font-bold font-mono" style={{ color }}>{value}</div>
            <div className="text-xs text-white/40 font-mono mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* By Class */}
      <div className="rounded-xl p-5" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-4">Capacity by Class</div>
        <div className="space-y-2">
          {classes.map(([cls, data]) => {
            const pct = ((data.count / fleet.total) * 100).toFixed(0);
            const util = data.totalCap > 0 ? ((data.totalLoad / data.totalCap) * 100).toFixed(1) : 0;
            return (
              <div key={cls}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-white/80 font-mono">{cls}</span>
                  <span className="text-white/50 font-mono">{data.count} vessels · {fmtNum(data.totalCap)} TEU · {util}% util</span>
                </div>
                <div className="w-full h-2 rounded-full bg-white/5 overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${pct}%`, background: "linear-gradient(90deg, rgba(0,212,255,0.5), #00d4ff)" }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Regional deployment */}
      <div className="grid grid-cols-5 gap-3">
        {Object.entries(fleet.byRegion).map(([reg, data]) => {
          const color = { Asia: '#00d4ff', Europe: '#7c3aed', Americas: '#10b981', 'Middle East': '#f59e0b', Africa: '#ef4444' }[reg] || '#00d4ff';
          const utilPct = data.totalCap > 0 ? ((data.totalLoad / data.totalCap) * 100).toFixed(1) : 0;
          return (
            <div key={reg} className="rounded-xl p-3 text-center" style={{ background: `${color}08`, border: `1px solid ${color}22` }}>
              <div className="text-[10px] font-mono font-bold" style={{ color }}>{reg}</div>
              <div className="text-lg font-bold font-mono text-white/90 mt-1">{data.count}</div>
              <div className="text-[9px] text-white/40 font-mono">vessels</div>
              <div className="text-[10px] text-white/50 font-mono mt-1">{(data.totalLoad / 1000).toFixed(0)}K / {(data.totalCap / 1000).toFixed(0)}K TEU</div>
              <div className="text-[9px] font-mono" style={{ color: parseFloat(utilPct) > 90 ? '#10b981' : '#f59e0b' }}>{utilPct}% util</div>
            </div>
          );
        })}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <input type="text" placeholder="Search vessels..."
          value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
          className="flex-1 px-3 py-1.5 rounded-lg text-xs font-mono bg-white/5 border border-white/10 text-white/80 placeholder-white/30 focus:outline-none focus:border-cyan-400/50" />
        <select value={classFilter} onChange={e => setClassFilter(e.target.value)}
          className="px-3 py-1.5 rounded-lg text-xs font-mono bg-white/5 border border-white/10 text-white/80">
          <option value="all">All Classes</option>
          {classes.map(([c]) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={regionFilter} onChange={e => setRegionFilter(e.target.value)}
          className="px-3 py-1.5 rounded-lg text-xs font-mono bg-white/5 border border-white/10 text-white/80">
          <option value="all">All Regions</option>
          {Object.keys(fleet.byRegion).map(r => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      {/* Sortable vessel table */}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.07)" }}>
        <table className="w-full" aria-label="Fleet vessel table">
          <thead>
            <tr style={{ background: "rgba(255,255,255,0.03)" }}>
              <SortHeader k="id" label="Service" />
              <SortHeader k="load" label="Load" />
              <SortHeader k="capacity" label="Capacity" />
              <SortHeader k="util" label="Util %" />
              <SortHeader k="profit" label="Profit" />
              <th className="text-left px-2 py-1.5 text-[10px] font-mono text-white/40 uppercase tracking-wider">Class</th>
              <th className="text-left px-2 py-1.5 text-[10px] font-mono text-white/40 uppercase tracking-wider">Region</th>
              <th className="text-left px-2 py-1.5 text-[10px] font-mono text-white/40 uppercase tracking-wider">Route</th>
            </tr>
          </thead>
          <tbody>
            {filteredVessels.slice(0, 100).map((s, i) => (
              <tr key={s.id} className="transition-colors hover:bg-white/5" style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}>
                <td className="px-2 py-1.5 text-[10px] font-mono text-cyan-400">{s.id}</td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-white/80">{fmtNum(s.load)}</td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-white/80">{fmtNum(s.capacity)}</td>
                <td className="px-2 py-1.5 text-[10px] font-mono" style={{ color: (s.load / s.capacity) > 0.9 ? '#10b981' : '#f59e0b' }}>
                  {s.capacity > 0 ? ((s.load / s.capacity) * 100).toFixed(0) : 0}%
                </td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-emerald-400">${(s.weekly_profit / 1000).toFixed(0)}K</td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-white/60">{s.vessel_class}</td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-white/60">{s.region}</td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-white/40">{s.ports?.[0]} → {s.ports?.[s.ports.length - 1]}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredVessels.length > 100 && (
          <div className="text-center py-2 text-[10px] text-white/30 font-mono">Showing 100 of {filteredVessels.length} vessels</div>
        )}
      </div>
    </div>
  );
}
