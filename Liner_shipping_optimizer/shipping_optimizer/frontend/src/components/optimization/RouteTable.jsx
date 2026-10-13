import { useMemo, useState } from 'react';
import { fmt, fmtNum } from '../../utils/formatters.js';

export default function RouteTable({ optimizationState }) {
  const [sortKey, setSortKey] = useState('profit');
  const [sortDir, setSortDir] = useState('desc');
  const [searchTerm, setSearchTerm] = useState('');
  const [regionFilter, setRegionFilter] = useState('all');
  const [page, setPage] = useState(0);
  const perPage = 25;
  const [selectedService, setSelectedService] = useState(null);

  const services = useMemo(() => optimizationState.global.selected_services || [], [optimizationState.global.selected_services]);

  const filtered = useMemo(() => {
    let list = services;
    if (regionFilter !== 'all') list = list.filter(s => s.region === regionFilter);
    if (searchTerm) {
      const t = searchTerm.toLowerCase();
      list = list.filter(s => s.id?.toLowerCase().includes(t) || s.ports?.some(p => p.toLowerCase().includes(t)));
    }
    list = [...list].sort((a, b) => {
      const av = sortKey === 'profit' ? (a.weekly_profit || 0) : sortKey === 'load' ? (a.load || 0) : sortKey === 'capacity' ? (a.capacity || 0) : sortKey === 'margin' ? (a.margin_pct || 0) : sortKey === 'rev' ? (a.revenue || 0) : 0;
      const bv = sortKey === 'profit' ? (b.weekly_profit || 0) : sortKey === 'load' ? (b.load || 0) : sortKey === 'capacity' ? (b.capacity || 0) : sortKey === 'margin' ? (b.margin_pct || 0) : sortKey === 'rev' ? (b.revenue || 0) : 0;
      return sortDir === 'asc' ? av - bv : bv - av;
    });
    return list;
  }, [services, regionFilter, searchTerm, sortKey, sortDir]);

  const totalPages = Math.ceil(filtered.length / perPage);
  const pageList = filtered.slice(page * perPage, (page + 1) * perPage);

  const SortHeader = ({ k, label }) => (
    <th className="text-left px-2 py-1.5 text-[10px] font-mono text-white/40 uppercase tracking-wider cursor-pointer select-none"
      onClick={() => { if (sortKey === k) setSortDir(d => d === 'asc' ? 'desc' : 'asc'); else { setSortKey(k); setSortDir('desc'); } }}
      aria-sort={sortKey === k ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      {label} {sortKey === k ? (sortDir === 'asc' ? '▲' : '▼') : '▽'}
    </th>
  );

  if (!services.length) {
    return <div className="text-white/40 font-mono italic text-center py-8">Route data not available</div>;
  }

  const regions = [...new Set(services.map(s => s.region).filter(Boolean))];

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Routes', value: fmtNum(services.length), color: '#00d4ff' },
          { label: 'Total Weekly Profit', value: fmt(services.reduce((s, sv) => s + (sv.weekly_profit || 0), 0)), color: '#10b981' },
          { label: 'Total TEU Moved', value: `${(services.reduce((s, sv) => s + (sv.load || 0), 0) / 1000).toFixed(0)}K`, color: '#8b5cf6' },
          { label: 'Avg Load Factor', value: services.length ? `${(services.reduce((s, sv) => s + (sv.load || 0), 0) / services.reduce((s, sv) => s + (sv.capacity || 0), 0) * 100).toFixed(1)}%` : '—', color: '#f59e0b' },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-xl p-3 text-center" style={{ background: `${color}08`, border: `1px solid ${color}22` }}>
            <div className="text-lg font-bold font-mono" style={{ color }}>{value}</div>
            <div className="text-[10px] text-white/40 font-mono">{label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <input type="text" placeholder="Search by ID or port..."
          value={searchTerm} onChange={e => { setSearchTerm(e.target.value); setPage(0); }}
          className="flex-1 px-3 py-1.5 rounded-lg text-xs font-mono bg-white/5 border border-white/10 text-white/80 placeholder-white/30 focus:outline-none focus:border-cyan-400/50"
          aria-label="Search routes" />
        <select value={regionFilter} onChange={e => { setRegionFilter(e.target.value); setPage(0); }}
          className="px-3 py-1.5 rounded-lg text-xs font-mono bg-white/5 border border-white/10 text-white/80" aria-label="Filter by region">
          <option value="all">All Regions</option>
          {regions.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.07)" }} role="table" aria-label="Route explorer table">
        <table className="w-full">
          <thead><tr style={{ background: "rgba(255,255,255,0.03)" }}>
            <SortHeader k="id" label="Route ID" />
            <th className="text-left px-2 py-1.5 text-[10px] font-mono text-white/40 uppercase tracking-wider">Ports</th>
            <SortHeader k="load" label="Load" />
            <SortHeader k="capacity" label="Capacity" />
            <th className="text-left px-2 py-1.5 text-[10px] font-mono text-white/40 uppercase tracking-wider">Util</th>
            <SortHeader k="profit" label="Profit" />
            <SortHeader k="margin" label="Margin" />
            <th className="text-left px-2 py-1.5 text-[10px] font-mono text-white/40 uppercase tracking-wider">Class</th>
            <th className="text-left px-2 py-1.5 text-[10px] font-mono text-white/40 uppercase tracking-wider">Region</th>
          </tr></thead>
          <tbody>
            {pageList.map((s, i) => (
              <tr key={s.id}
                onClick={() => setSelectedService(selectedService?.id === s.id ? null : s)}
                className="transition-colors cursor-pointer"
                style={{ borderTop: "1px solid rgba(255,255,255,0.04)", background: selectedService?.id === s.id ? 'rgba(0,212,255,0.06)' : undefined }}
                tabIndex={0} role="row" aria-label={`Route ${s.id}`}>
                <td className="px-2 py-1.5 text-[10px] font-mono text-cyan-400">{s.id}</td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-white/60">{s.ports?.join(' → ')}</td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-white/80">{fmtNum(s.load)} TEU</td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-white/80">{fmtNum(s.capacity)} TEU</td>
                <td className="px-2 py-1.5 text-[10px] font-mono" style={{ color: s.capacity && (s.load / s.capacity) > 0.9 ? '#10b981' : '#f59e0b' }}>
                  {s.capacity ? ((s.load / s.capacity) * 100).toFixed(0) : 0}%
                </td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-emerald-400">${(s.weekly_profit / 1000).toFixed(0)}K</td>
                <td className="px-2 py-1.5 text-[10px] font-mono" style={{ color: (s.margin_pct || 0) > 50 ? '#10b981' : (s.margin_pct || 0) > 0 ? '#f59e0b' : '#ef4444' }}>
                  {s.margin_pct?.toFixed(1)}%
                </td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-white/60">{s.vessel_class}</td>
                <td className="px-2 py-1.5 text-[10px] font-mono text-white/60">{s.region}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        <div className="flex items-center justify-between px-3 py-2 border-t border-white/5">
          <span className="text-[10px] text-white/30 font-mono">{filtered.length} routes total</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}
              className="px-2 py-1 text-[10px] font-mono rounded disabled:opacity-30 bg-white/5 text-white/60" aria-label="Previous page">◀</button>
            <span className="text-[10px] text-white/50 font-mono">{page + 1} / {totalPages || 1}</span>
            <button onClick={() => setPage(Math.min(totalPages - 1, page + 1))} disabled={page >= totalPages - 1}
              className="px-2 py-1 text-[10px] font-mono rounded disabled:opacity-30 bg-white/5 text-white/60" aria-label="Next page">▶</button>
          </div>
        </div>
      </div>

      {/* Service detail panel */}
      {selectedService && (
        <div className="rounded-xl p-5" style={{ background: "rgba(0,212,255,0.04)", border: "1px solid rgba(0,212,255,0.2)" }}>
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs font-mono font-bold text-cyan-400">{selectedService.id}</div>
            <button onClick={() => setSelectedService(null)} className="text-[10px] text-white/30 font-mono hover:text-white/60" aria-label="Close detail">✕</button>
          </div>
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Route', value: selectedService.ports?.join(' → ') || '—', color: '#00d4ff' },
              { label: 'Vessel Class', value: selectedService.vessel_class || '—', color: '#8b5cf6' },
              { label: 'Load / Capacity', value: `${fmtNum(selectedService.load)} / ${fmtNum(selectedService.capacity)} TEU`, color: '#10b981' },
              { label: 'Utilization', value: selectedService.capacity ? `${((selectedService.load / selectedService.capacity) * 100).toFixed(1)}%` : '—', color: '#f59e0b' },
              { label: 'Weekly Profit', value: fmt(selectedService.weekly_profit || 0), color: '#10b981' },
              { label: 'Profit Margin', value: `${(selectedService.margin_pct || 0).toFixed(1)}%`, color: (selectedService.margin_pct || 0) > 0 ? '#10b981' : '#ef4444' },
              { label: 'Revenue', value: fmt(selectedService.revenue || 0), color: '#00d4ff' },
              { label: 'Cost', value: fmt(selectedService.cost || 0), color: '#ef4444' },
              { label: 'Region', value: selectedService.region || '—', color: '#6366f1' },
              { label: 'Port Calls', value: `${selectedService.ports?.length || 0} ports`, color: '#ec4899' },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-lg p-2" style={{ background: `${color}08`, border: `1px solid ${color}22` }}>
                <div className="text-[9px] text-white/40 font-mono uppercase tracking-wider">{label}</div>
                <div className="text-xs font-mono font-bold mt-0.5" style={{ color }}>{value}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
