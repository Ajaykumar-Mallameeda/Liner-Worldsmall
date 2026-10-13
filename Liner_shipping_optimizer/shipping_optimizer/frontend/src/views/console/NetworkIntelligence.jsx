/**
 * NetworkIntelligence.jsx
 * -----------------------
 * Full-fidelity Network Topology Exploration & Single-Service Inspection View.
 *
 * Capabilities:
 * 1. Region View Mode:
 *    - Filter by [ WORLD | AMERICAS | EUROPE | MIDDLE EAST | ASIA PACIFIC | AFRICA ]
 *    - Deterministic, identical region colors across map routes, markers, badges, and tables.
 *    - All services and port markers strictly filtered by the active region.
 * 2. Single Service Inspection Mode:
 *    - Clicking any service in the table switches the map into SINGLE SERVICE MODE.
 *    - Unrelated routes and port markers disappear.
 *    - The selected service route sequence (Origin → Waypoints → Destination) is rendered.
 *    - Mandatory port labels with Port Name, Code, and TEU load.
 *    - Service Detail Side Panel opens to the right of the map.
 *    - Clear / Back button restores the active region view.
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useOptimizationState } from '../../hooks/useOptimizationState.js';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import WorldMap, { getRegionColor } from '../../components/map/WorldMap.jsx';
import ServiceDetailPanel from '../../components/console/ServiceDetailPanel.jsx';
import { Pill, Kv, Stat, Empty, Provenance } from '../../components/console/p12.jsx';
import { fmtNum, fmtPct, fmtUsd } from '../../utils/formatters.js';

const REGIONS = [
  { id: 'world',       label: 'WORLD',        color: '#00d4ff' },
  { id: 'americas',    label: 'AMERICAS',     color: '#10b981' },
  { id: 'europe',      label: 'EUROPE',       color: '#7c3aed' },
  { id: 'middle_east', label: 'MIDDLE EAST',  color: '#f59e0b' },
  { id: 'asia',        label: 'ASIA PACIFIC', color: '#00d4ff' },
  { id: 'africa',      label: 'AFRICA',       color: '#ef4444' },
];

export default function NetworkIntelligence({
  optimizationState: optStateProp,
  runtime: runtimeProp,
  maritimeOverview,
}) {
  const hookState = useOptimizationState();
  const optState = (runtimeProp && runtimeProp.global) ? runtimeProp : (optStateProp || hookState);
  const sm = optState?.global || {};

  const [activeRegion, setActiveRegion] = useState('world');
  const [selectedService, setSelectedService] = useState(null);
  const [routingImpact, setRoutingImpact] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch routing impact if available
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch('/api/maritime/routing-impact');
        if (r.ok && !cancelled) {
          const j = await r.json();
          if (j && !j.reason) setRoutingImpact(j);
        }
      } catch (_) { /* noop */ }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  // All selected services from pipeline_output.json
  const allServices = useMemo(() => {
    return sm.selected_services || [];
  }, [sm.selected_services]);

  // Region matching helper
  const matchesRegion = useCallback((svcRegion, targetRegion) => {
    if (!targetRegion || targetRegion === 'world') return true;
    const r = String(svcRegion || '').toLowerCase();
    const t = String(targetRegion).toLowerCase();
    if (t === 'americas') return r.includes('americ');
    if (t === 'europe') return r.includes('europ');
    if (t === 'middle_east' || t === 'middle east') return r.includes('middl') || r.includes('east');
    if (t === 'asia' || t === 'asia pacific') return r.includes('asia') || r.includes('pacif');
    if (t === 'africa') return r.includes('afric');
    return r === t;
  }, []);

  // Filter services by active region
  const regionServices = useMemo(() => {
    if (activeRegion === 'world') return allServices;
    return allServices.filter((s) => matchesRegion(s.region, activeRegion));
  }, [allServices, activeRegion, matchesRegion]);

  // Search filtered services
  const displayedServices = useMemo(() => {
    if (!searchQuery.trim()) return regionServices;
    const q = searchQuery.toLowerCase().trim();
    return regionServices.filter(
      (s) =>
        (s.id && s.id.toLowerCase().includes(q)) ||
        (s.vessel_class && s.vessel_class.toLowerCase().includes(q)) ||
        (s.ports && s.ports.some((p) => p.toLowerCase().includes(q)))
    );
  }, [regionServices, searchQuery]);

  // Regional breakdown statistics
  const regionStats = useMemo(() => {
    const m = {};
    allServices.forEach((s) => {
      const r = (s.region || 'Unknown').toLowerCase();
      const normKey = r.includes('americ') ? 'americas' :
                      r.includes('europ') ? 'europe' :
                      r.includes('middl') || r.includes('east') ? 'middle_east' :
                      r.includes('asia') || r.includes('pacif') ? 'asia' :
                      r.includes('afric') ? 'africa' : 'other';
      if (!m[normKey]) {
        m[normKey] = {
          name: s.region || 'Asia Pacific',
          services: 0,
          profit: 0,
          ports: new Set(),
          color: getRegionColor(s.region),
        };
      }
      m[normKey].services += 1;
      m[normKey].profit += Number(s.weekly_profit || 0);
      (s.ports || []).forEach((p) => m[normKey].ports.add(p));
    });
    return m;
  }, [allServices]);

  // Handle region filter change: reset selected service
  const handleRegionChange = (newRegion) => {
    setActiveRegion(newRegion);
    setSelectedService(null);
  };

  // Clear single service selection and return to active region view
  const handleClearService = () => {
    setSelectedService(null);
  };

  const totalSelected = allServices.length;
  const activeRegionObj = REGIONS.find((r) => r.id === activeRegion) || REGIONS[0];
  const activeRegionColor = activeRegionObj.color;

  return (
    <div className="cx-page-body space-y-3 select-none font-mono">
      {/* ══ PAGE HEAD ══ */}
      <PageHead
        section="Intelligence"
        eyebrow="Network Topology"
        title="Network Intelligence"
        subtitle="Interactive maritime route exploration and single-service inspection. Filter by region or click any service in the table to inspect its isolated port sequence and runtime telemetry."
        pills={[
          { tone: totalSelected > 0 ? 'available' : 'no_data', label: `${totalSelected} services on disk` },
          { tone: selectedService ? 'selected' : 'converged', label: selectedService ? `INSPECTING ${selectedService.id}` : `${activeRegionObj.label} VIEW` },
        ]}
      />

      {/* ══ REGION FILTER TOOLBAR ══ */}
      <div className="flex items-center justify-between p-2 rounded bg-black/60 border border-white/10 backdrop-blur-md">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[8.5px] text-slate-400 font-bold uppercase tracking-widest mr-2">REGION FILTER:</span>
          {REGIONS.map((r) => {
            const isActive = activeRegion === r.id;
            const count = r.id === 'world' ? totalSelected : allServices.filter((s) => matchesRegion(s.region, r.id)).length;
            return (
              <button
                key={r.id}
                type="button"
                onClick={() => handleRegionChange(r.id)}
                className={`px-3 py-1 text-[9px] font-bold tracking-wider uppercase rounded transition-all flex items-center gap-1.5 border ${
                  isActive
                    ? 'shadow-lg'
                    : 'bg-white/[0.02] border-white/5 text-slate-400 hover:text-white hover:bg-white/5'
                }`}
                style={
                  isActive
                    ? {
                        background: `${r.color}25`,
                        borderColor: r.color,
                        color: r.color,
                        boxShadow: `0 0 10px ${r.color}35`,
                      }
                    : {}
                }
              >
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: r.color }} />
                <span>{r.label}</span>
                <span className="text-[8px] opacity-75 font-normal">({count})</span>
              </button>
            );
          })}
        </div>

        {selectedService && (
          <button
            type="button"
            onClick={handleClearService}
            className="text-[9px] px-2.5 py-1 rounded bg-amber-500/20 border border-amber-500/50 text-amber-300 font-bold uppercase hover:bg-amber-500/30 transition-colors"
          >
            ✕ CLEAR SERVICE INSPECTION
          </button>
        )}
      </div>

      {/* ══ TOP SECTION: MAP + SERVICE DETAIL PANEL ══ */}
      <div className="grid grid-cols-12 gap-3 items-stretch">
        {/* Left Column: World Map */}
        <div className={selectedService ? 'col-span-8' : 'col-span-12'}>
          <InstrumentPanel
            title={
              selectedService
                ? `Single Service Route — ${selectedService.id}`
                : `Network Canvas — ${activeRegionObj.label} (${regionServices.length} Services)`
            }
            right={
              selectedService ? (
                <span className="text-cyan-400 font-bold text-[9px]">
                  ● SINGLE SERVICE INSPECTION · {selectedService.ports.join(' → ')}
                </span>
              ) : (
                <span className="text-slate-400 text-[8.5px]">
                  {activeRegionObj.label} · {regionServices.length} SELECTED
                </span>
              )
            }
            bodyPadding="flush"
          >
            <div style={{ height: selectedService ? 440 : 460 }}>
              <WorldMap
                optimizationState={optState}
                selectedServices={regionServices}
                inspectedService={selectedService}
                regionFilter={activeRegion}
                onSelectService={setSelectedService}
                onClearService={handleClearService}
              />
            </div>
          </InstrumentPanel>
        </div>

        {/* Right Column: Service Detail Side Panel (Only in Single Service Mode) */}
        {selectedService && (
          <div className="col-span-4">
            <InstrumentPanel
              title={`Service Details — ${selectedService.id}`}
              right={<span className="text-emerald-400 font-bold text-[8.5px]">LIVE RUNTIME</span>}
              bodyPadding="flush"
            >
              <div style={{ maxHeight: 440, overflowY: 'auto' }}>
                <ServiceDetailPanel service={selectedService} onClose={handleClearService} />
              </div>
            </InstrumentPanel>
          </div>
        )}
      </div>

      {/* ══ BOTTOM SECTION: SELECTED SERVICES TABLE + REGIONAL SPLIT ══ */}
      <div className="grid grid-cols-12 gap-3 items-stretch">
        {/* Left: Selected Services Table (8-cols) */}
        <div className="col-span-8 flex flex-col h-full">
          <InstrumentPanel
            title={`Selected Services (${regionServices.length} in ${activeRegionObj.label})`}
            right={
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Filter by ID, vessel, port..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="px-2 py-0.5 text-[8.5px] rounded bg-black/60 border border-white/10 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-400 font-mono w-44"
                />
                <span className="text-[8.5px] text-slate-400">
                  {displayedServices.length} / {regionServices.length}
                </span>
              </div>
            }
            bodyPadding="flush"
            style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
          >
            {displayedServices.length === 0 ? (
              <div className="p-8 text-center flex-1 flex items-center justify-center">
                <Empty
                  tone="no_data"
                  label="no services"
                  title={`No selected services found in ${activeRegionObj.label}`}
                  hint="Select a different region or clear the search filter."
                />
              </div>
            ) : (
              <div className="cx-table flex-1 flex flex-col">
                <div className="cx-rows flex-1" style={{ height: 410, maxHeight: 410, overflowY: 'auto' }}>
                  {/* Table Header */}
                  <div
                    className="cx-row sticky top-0 bg-[#060c14] z-10 font-bold text-[8.5px] tracking-wider text-slate-400 border-b border-white/10"
                    style={{ display: 'grid', gridTemplateColumns: '120px 100px 100px 1fr 100px 80px', padding: '6px 10px' }}
                  >
                    <div>SERVICE ID</div>
                    <div>REGION</div>
                    <div>VESSEL</div>
                    <div>PORT SEQUENCE</div>
                    <div style={{ textAlign: 'right' }}>WEEKLY P&amp;L</div>
                    <div style={{ textAlign: 'right' }}>MARGIN</div>
                  </div>

                  {/* Table Rows */}
                  {displayedServices.map((s) => {
                    const isSelected = selectedService && selectedService.id === s.id;
                    const rColor = getRegionColor(s.region);

                    return (
                      <div
                        key={s.id}
                        className={`cx-row transition-all text-[9px] hover:bg-white/[0.04] ${
                          isSelected ? 'bg-cyan-950/40' : ''
                        }`}
                        onClick={() => setSelectedService(s)}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '120px 100px 100px 1fr 100px 80px',
                          padding: '6px 10px',
                          cursor: 'pointer',
                          borderLeft: isSelected ? `3px solid ${rColor}` : '3px solid transparent',
                        }}
                      >
                        {/* Service ID */}
                        <div className="font-bold flex items-center gap-1.5" style={{ color: isSelected ? '#00d4ff' : '#f1f5f9' }}>
                          <span className="w-1.5 h-1.5 rounded-full" style={{ background: rColor }} />
                          <span>{s.id}</span>
                        </div>

                        {/* Region Badge */}
                        <div>
                          <span
                            className="text-[7.5px] px-1.5 py-0.5 rounded font-semibold uppercase"
                            style={{ background: `${rColor}20`, color: rColor }}
                          >
                            {s.region || 'Asia Pacific'}
                          </span>
                        </div>

                        {/* Vessel */}
                        <div className="text-slate-300 truncate">{s.vessel_class || 'Standard'}</div>

                        {/* Port Sequence */}
                        <div className="text-slate-300 truncate font-semibold">
                          {(s.ports || []).join(' → ')}
                          <span className="text-slate-500 font-normal text-[8px] ml-1">({fmtNum(s.load)} TEU)</span>
                        </div>

                        {/* Profit */}
                        <div className="text-right font-bold text-emerald-400">
                          {fmtUsd(s.weekly_profit)}
                        </div>

                        {/* Margin */}
                        <div className="text-right text-cyan-300 font-semibold">
                          {s.margin_pct != null ? fmtPct(s.margin_pct) : '—'}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </InstrumentPanel>
        </div>

        {/* Right: Regional Split & Routing Impact (4-cols) */}
        <div className="col-span-4 flex flex-col justify-between h-full space-y-3">
          {/* Regional Split Breakdown */}
          <InstrumentPanel
            title="Regional Split Breakdown"
            right={<span className="text-[8px] text-slate-400 uppercase">5 REGIONS ON DISK</span>}
            bodyPadding="flush"
            style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
          >
            <div className="divide-y divide-white/5 flex-1 flex flex-col justify-between">
              {Object.entries(regionStats).map(([rKey, st]) => {
                const isCurrent = activeRegion === rKey;
                return (
                  <div
                    key={rKey}
                    onClick={() => handleRegionChange(rKey)}
                    className={`p-2.5 hover:bg-white/[0.03] cursor-pointer transition-colors flex-1 flex flex-col justify-center ${
                      isCurrent ? 'bg-white/[0.04]' : ''
                    }`}
                  >
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-bold text-[9.5px] uppercase flex items-center gap-1.5" style={{ color: st.color }}>
                        <span className="w-2 h-2 rounded-full" style={{ background: st.color }} />
                        {st.name}
                      </span>
                      <span className="text-[8.5px] text-slate-300 font-bold">{st.services} services</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[8.5px]">
                      <div>
                        <span className="text-slate-500">P&amp;L: </span>
                        <span className="text-emerald-400 font-bold">{fmtUsd(st.profit)}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-slate-500">PORTS: </span>
                        <span className="text-slate-200 font-bold">{st.ports.size} ports</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </InstrumentPanel>

          {/* Routing Impact Card */}
          <InstrumentPanel
            title="Routing Impact"
            right={<Pill tone={routingImpact && !routingImpact.reason ? 'available' : 'no_data'}>{routingImpact && !routingImpact.reason ? 'on disk' : 'no data'}</Pill>}
            style={{ flex: '0 0 auto' }}
          >
            {routingImpact && !routingImpact.reason ? (
              <div className="grid grid-cols-2 gap-2">
                <Stat k="maritime features" v={routingImpact.maritime_features_attached ?? '—'} variant="accent" />
                <Stat k="affected decision" v={routingImpact.affected_decision == null ? '—' : String(routingImpact.affected_decision)} />
                <Stat k="quality score" v={routingImpact.quality != null ? Number(routingImpact.quality).toFixed(2) : '—'} />
                <Stat k="freshness state" v={routingImpact.freshness_state || routingImpact.state || '—'} />
              </div>
            ) : (
              <div className="p-2 text-[8.5px] text-slate-400 leading-relaxed">
                <div className="text-slate-300 font-semibold mb-1">● NOT OBSERVED</div>
                Routing impact analysis has not produced causal diffs for this run.
              </div>
            )}
          </InstrumentPanel>
        </div>
      </div>

      {/* ══ PROVENANCE FOOTER ══ */}
      <Provenance
        source="pipeline_output.json (selected_services, regional_results) + maritime snapshot store"
        sourceStatus={totalSelected > 0 ? 'available' : 'no_data'}
        attribution="EMODnet, NOAA MarineCadastre, Open-Meteo, Fintraffic Digitraffic"
        license="Mixed open-data / non-commercial"
        recordCount={totalSelected}
      />
    </div>
  );
}
