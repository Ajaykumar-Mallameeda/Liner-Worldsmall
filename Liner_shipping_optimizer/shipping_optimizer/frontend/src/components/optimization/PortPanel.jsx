import { useMemo, useState } from 'react';
import { fmtNum } from '../../utils/formatters.js';

export default function PortPanel({ optimizationState }) {
  const [selectedPort, setSelectedPort] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  const portData = useMemo(() => {
    const svcs = optimizationState.global.selected_services || [];
    const ports = {};
    const allHubs = new Set();
    Object.values(optimizationState.regions).forEach(r => (r.hubs || []).forEach(h => allHubs.add(h)));

    svcs.forEach(s => {
      (s.ports || []).forEach((p, i) => {
        if (!ports[p]) ports[p] = { id: p, inbound: 0, outbound: 0, services: new Set(), regions: new Set(), totalTeu: 0 };
        ports[p].services.add(s.id);
        ports[p].regions.add(s.region);
        ports[p].totalTeu += s.load || 0;
        if (i === 0) ports[p].outbound++;
        if (i === s.ports.length - 1) ports[p].inbound++;
        if (i > 0 && i < s.ports.length - 1) { ports[p].inbound++; ports[p].outbound++; }
      });
    });

    return Object.entries(ports)
      .map(([id, d]) => ({
        id,
        serviceCount: d.services.size,
        inbound: d.inbound,
        outbound: d.outbound,
        totalTeu: d.totalTeu,
        regions: [...d.regions],
        isHub: allHubs.has(id),
        importance: (d.services.size * 2 + d.totalTeu / 1000) | 0,
      }))
      .sort((a, b) => b.importance - a.importance);
  }, [optimizationState.global.selected_services, optimizationState.regions]);

  const filtered = useMemo(() => {
    if (!searchTerm) return portData;
    const t = searchTerm.toLowerCase();
    return portData.filter(p => p.id.toLowerCase().includes(t));
  }, [portData, searchTerm]);

  const selPort = selectedPort ? portData.find(p => p.id === selectedPort) : null;

  if (!portData.length) {
    return <div className="text-white/40 font-mono italic text-center py-8">Port data not available</div>;
  }

  return (
    <div className="flex gap-4 h-full">
      {/* Port list */}
      <div className="w-72 flex-shrink-0 flex flex-col gap-3">
        <input type="text" placeholder="Search port..."
          value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
          className="px-3 py-1.5 rounded-lg text-xs font-mono bg-white/5 border border-white/10 text-white/80 placeholder-white/30 focus:outline-none focus:border-cyan-400/50"
          aria-label="Search ports" />
        <div className="flex-1 overflow-y-auto space-y-1 pr-1">
          {filtered.slice(0, 100).map(p => (
            <button key={p.id} onClick={() => setSelectedPort(p.id)}
              className="w-full text-left px-3 py-2 rounded-lg transition-all text-[11px] font-mono"
              style={{
                background: selectedPort === p.id ? `${p.isHub ? '#f59e0b' : '#00d4ff'}12` : 'rgba(255,255,255,0.02)',
                border: `1px solid ${selectedPort === p.id ? `${p.isHub ? '#f59e0b' : '#00d4ff'}33` : 'rgba(255,255,255,0.06)'}`,
              }}
              aria-label={`Port ${p.id}${p.isHub ? ', hub port' : ''}`}>
              <div className="flex items-center justify-between">
                <span className="font-bold" style={{ color: p.isHub ? '#f59e0b' : '#00d4ff' }}>
                  {p.id} {p.isHub ? '★' : ''}
                </span>
                <span className="text-[9px] text-white/30">{p.serviceCount} routes</span>
              </div>
              <div className="flex justify-between text-[9px] text-white/40 mt-0.5">
                <span>{(p.totalTeu / 1000).toFixed(0)}K TEU</span>
                <span>Score: {p.importance}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Port detail */}
      <div className="flex-1">
        {selPort ? (
          <div className="rounded-xl p-5" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)" }}>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: selPort.isHub ? '#f59e0b' : '#00d4ff', boxShadow: `0 0 8px ${selPort.isHub ? '#f59e0b' : '#00d4ff'}` }} />
              <h2 className="text-sm font-bold font-mono" style={{ color: selPort.isHub ? '#f59e0b' : '#00d4ff' }}>
                {selPort.id} {selPort.isHub ? '(Hub Port)' : ''}
              </h2>
            </div>
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: 'Weekly Throughput', value: `${(selPort.totalTeu / 1000).toFixed(0)}K TEU`, color: '#00d4ff' },
                { label: 'Connected Regions', value: selPort.regions.length.toString(), color: '#10b981' },
                { label: 'Service Count', value: selPort.serviceCount.toString(), color: '#8b5cf6' },
                { label: 'Importance Score', value: selPort.importance.toString(), color: '#f59e0b' },
                { label: 'Inbound Routes', value: selPort.inbound.toString(), color: '#6366f1' },
                { label: 'Outbound Routes', value: selPort.outbound.toString(), color: '#ec4899' },
              ].map(({ label, value, color }) => (
                <div key={label} className="rounded-lg p-3" style={{ background: `${color}08`, border: `1px solid ${color}22` }}>
                  <div className="text-[9px] text-white/40 font-mono uppercase tracking-wider">{label}</div>
                  <div className="text-lg font-bold font-mono mt-1" style={{ color }}>{value}</div>
                </div>
              ))}
            </div>
            {selPort.regions.length > 0 && (
              <div className="mt-3">
                <div className="text-[10px] text-white/30 font-mono uppercase tracking-widest mb-2">Connected Regions</div>
                <div className="flex gap-2">
                  {selPort.regions.map(r => (
                    <span key={r} className="px-2 py-1 rounded text-[10px] font-mono" style={{ background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)' }}>{r}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-3xl mb-2 opacity-20">⚓</div>
              <div className="text-xs text-white/30 font-mono italic">Select a port to view details</div>
              <div className="text-[10px] text-white/20 font-mono mt-1">{portData.length} ports loaded</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
