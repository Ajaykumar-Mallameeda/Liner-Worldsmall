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

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { motionLevel } from '../../services/prefsStore.js';
import { useOptimizationState } from '../../hooks/useOptimizationState.js';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import WorldMap, { getRegionColor } from '../../components/map/WorldMap.jsx';
import ServiceDetailPanel from '../../components/console/ServiceDetailPanel.jsx';
import PortDetailPanel from '../../components/console/PortDetailPanel.jsx';
import BottomSheet, { useIsPhone } from '../../components/console/BottomSheet.jsx';
import { fetchDemand, ledgerForServices, datasetOf, portActivity } from '../../utils/portFlows.js';
import { useTransshipment } from '../../services/transshipmentData.js';
import { hubAt } from '../../utils/transshipment.js';
import { getPortName } from '../../utils/portLookup.js';
import { Pill, Kv, Stat, Empty, Provenance } from '../../components/console/p12.jsx';
import { fmtNum, fmtPct, fmtUsd } from '../../utils/formatters.js';
import { matchesAgent, setAgentFocus, useAgentFocus, useServiceRequest, hoverProps } from '../../services/focusStore.js';
import { usePresence } from '../../utils/motion.js';
import { downloadCsv } from '../../utils/exportData.js';

// Regions are geographic (utils/geoRegion.js): a service's region is where most of its ports are.
// The optimizer's regional-agent label is kept on each service as agent_region.
const REGIONS = [
  { id: 'world',       label: 'WORLD',        color: '#00d4ff', geo: null },
  { id: 'americas',    label: 'AMERICAS',     color: '#10b981', geo: 'Americas' },
  { id: 'europe',      label: 'EUROPE',       color: '#7c3aed', geo: 'Europe' },
  { id: 'middle_east', label: 'MIDDLE EAST',  color: '#f59e0b', geo: 'Middle East' },
  { id: 'asia',        label: 'ASIA PACIFIC', color: '#00d4ff', geo: 'Asia Pacific' },
  { id: 'africa',      label: 'AFRICA',       color: '#ef4444', geo: 'Africa' },
];
const REGION_ID_BY_GEO = Object.fromEntries(REGIONS.filter((r) => r.geo).map((r) => [r.geo, r.id]));

const SORTS = {
  pnl_desc: { label: 'P&L high → low', fn: (a, b) => Number(b.weekly_profit ?? -Infinity) - Number(a.weekly_profit ?? -Infinity) },
  pnl_asc:  { label: 'P&L low → high', fn: (a, b) => Number(a.weekly_profit ?? Infinity) - Number(b.weekly_profit ?? Infinity) },
  margin:   { label: 'Margin low → high', fn: (a, b) => Number(a.margin_pct ?? Infinity) - Number(b.margin_pct ?? Infinity) },
  id:       { label: 'Service ID', fn: (a, b) => String(a.id).localeCompare(String(b.id)) },
};
const pnlClass = (v) => (v == null ? 'text-slate-400' : Number(v) < 0 ? 'text-red-400' : 'text-emerald-400');

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
  const [focusPort, setFocusPort] = useState(null);   // port asked for from the palette: the map glides to it

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

  // All selected services from pipeline_output.json, narrowed to the agent cross-filter when one is set
  const [agentFocus] = useAgentFocus();
  const allServices = useMemo(() => {
    return (sm.selected_services || []).filter((s) => matchesAgent(s, agentFocus));
  }, [sm.selected_services, agentFocus]);

  // "Open service X" / "services calling port Y" from the command palette
  const [request, clearRequest] = useServiceRequest();
  useEffect(() => {
    if (!request || !sm.selected_services) return;
    if (request.kind === 'service') {
      const svc = sm.selected_services.find((s) => String(s.id) === request.id);
      if (svc) {
        if (!matchesAgent(svc, agentFocus)) setAgentFocus(null);
        setActiveRegion('world');
        setSelectedService(svc);
      }
    } else if (request.kind === 'port') {
      setActiveRegion('world');
      setSelectedService(null);
      setSearchQuery(request.id);
      setFocusPort(request.id);
      setOpenPort(request.id);   // also when the map is already on this port (no new glide to open it)
    }
    clearRequest();
  }, [request, sm.selected_services]); // eslint-disable-line react-hooks/exhaustive-deps

  const [sortKey, setSortKey] = useState('pnl_desc');
  const [lossOnly, setLossOnly] = useState(false);
  const lossCount = useMemo(() => allServices.filter((s) => Number(s.weekly_profit) < 0).length, [allServices]);
  // Inline bar scale: the largest |weekly P&L| among the services listed.
  const maxAbsPnl = useMemo(() => Math.max(1, ...allServices.map((s) => Math.abs(Number(s.weekly_profit) || 0))), [allServices]);

  // Region matching helper (geographic region of the service)
  const matchesRegion = useCallback((svcRegion, targetRegion) => {
    if (!targetRegion || targetRegion === 'world') return true;
    return REGION_ID_BY_GEO[svcRegion] === targetRegion;
  }, []);

  // Filter services by active region
  const regionServices = useMemo(() => {
    if (activeRegion === 'world') return allServices;
    return allServices.filter((s) => matchesRegion(s.region, activeRegion));
  }, [allServices, activeRegion, matchesRegion]);

  // Search filtered services
  const displayedServices = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    const list = regionServices.filter((s) => {
      if (lossOnly && !(Number(s.weekly_profit) < 0)) return false;
      if (!q) return true;
      return (s.id && s.id.toLowerCase().includes(q)) ||
        (s.vessel_class && s.vessel_class.toLowerCase().includes(q)) ||
        (s.ports && s.ports.some((p) => p.toLowerCase().includes(q)));
    });
    return [...list].sort(SORTS[sortKey].fn);
  }, [regionServices, searchQuery, lossOnly, sortKey]);

  // Regional breakdown statistics (geographic)
  const regionStats = useMemo(() => {
    const m = {};
    allServices.forEach((s) => {
      const normKey = REGION_ID_BY_GEO[s.region] || 'other';
      if (!m[normKey]) {
        m[normKey] = {
          name: s.region || 'Unknown',
          services: 0,
          losses: 0,
          profit: 0,
          ports: new Set(),
          color: getRegionColor(s.region),
        };
      }
      m[normKey].services += 1;
      if (Number(s.weekly_profit) < 0) m[normKey].losses += 1;
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

  // Port drawer and unserved layer: the run's routed flows against the dataset's lane demand (backend route).
  const [openPort, setOpenPort] = useState(null);
  const [showUnserved, setShowUnserved] = useState(true);
  const [demand, setDemand] = useState(undefined);   // undefined loading · null unavailable · object loaded
  const dataset = datasetOf(optState);
  useEffect(() => {
    let cancelled = false;
    setDemand(undefined);
    fetchDemand(dataset).then((d) => { if (!cancelled) setDemand(d || null); });
    return () => { cancelled = true; };
  }, [dataset]);
  // Flows come from the ledger of exactly the plan shown (the run's or one iteration's); with no such ledger the
  // per-port figures would describe another plan, so they are withheld.
  const ledger = useMemo(() => ledgerForServices(optState, sm.selected_services), [optState, sm.selected_services]);
  const flowsMatch = Boolean(ledger);
  const activity = useMemo(() => portActivity({
    flows: ledger?.plan?.flows || [],
    services: sm.selected_services || [],
    demand: ledger ? demand?.demand || null : null,
  }), [ledger, sm.selected_services, demand]);
  const transship = useTransshipment(optState);
  const unservedNote = !flowsMatch ? 'unserved: this plan has no matching routed flows'
    : demand === undefined ? 'unserved: loading demand…'
      : demand === null ? 'unserved: needs the backend (lane demand)' : null;

  const openPortDrawer = useCallback((code) => { setSelectedService(null); setOpenPort(code); }, []);
  const inspectService = useCallback((svc) => { setOpenPort(null); setSelectedService(svc); }, []);

  const totalSelected = allServices.length;
  // Detail column enters and leaves with the shared panel motion; it keeps the last service / port while closing.
  const detail = usePresence(Boolean(selectedService || openPort));
  const phone = useIsPhone();   // phones: details in a bottom sheet over the map (design D9)
  const mapBoxRef = useRef(null);
  const sheetOpen = Boolean(phone && (selectedService || openPort));
  // The half-height sheet leaves the top of the screen for the map: bring the map there when details open.
  useEffect(() => {
    if (!sheetOpen) return;
    const el = mapBoxRef.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top;
    if (top >= 0 && top < 140) return;   // already near the top
    el.scrollIntoView({ block: 'start', behavior: motionLevel() === 'full' ? 'smooth' : 'auto' });
  }, [sheetOpen, selectedService, openPort]);
  const lastService = React.useRef(null);
  const lastPort = React.useRef(null);
  if (selectedService) { lastService.current = selectedService; lastPort.current = null; }
  if (openPort) { lastPort.current = openPort; lastService.current = null; }
  const shownService = selectedService || (openPort ? null : lastService.current);
  const shownPort = openPort || (selectedService ? null : lastPort.current);
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
      <div className="flex items-center justify-between gap-2 flex-wrap p-2 rounded bg-black/60 border border-white/10 backdrop-blur-md">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[12px] text-slate-400 font-bold uppercase tracking-widest mr-2">REGION FILTER:</span>
          {REGIONS.map((r) => {
            const isActive = activeRegion === r.id;
            const count = r.id === 'world' ? totalSelected : allServices.filter((s) => matchesRegion(s.region, r.id)).length;
            const empty = count === 0 && !isActive;
            return (
              <button
                key={r.id}
                type="button"
                onClick={() => handleRegionChange(r.id)}
                disabled={empty}
                aria-pressed={isActive}
                title={empty ? `No selected service is mainly in ${r.label.toLowerCase()}` : undefined}
                className={`px-3 py-1 text-[12px] font-bold tracking-wider uppercase rounded transition-all flex items-center gap-1.5 border ${
                  isActive
                    ? 'shadow-lg'
                    : empty
                      ? 'bg-transparent border-white/5 text-slate-400 opacity-40 cursor-not-allowed'
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
                <span className="text-[12px] opacity-75 font-normal">({count})</span>
              </button>
            );
          })}
        </div>

        {selectedService && (
          <button
            type="button"
            onClick={handleClearService}
            className="text-[12px] px-2.5 py-1 rounded bg-amber-500/20 border border-amber-500/50 text-amber-300 font-bold uppercase hover:bg-amber-500/30 transition-colors"
          >
            ✕ CLEAR SERVICE INSPECTION
          </button>
        )}
      </div>

      {/* ══ TOP SECTION: MAP + SERVICE DETAIL PANEL ══ */}
      <div className="grid grid-cols-12 gap-3 items-stretch">
        {/* Left Column: World Map */}
        <div className={detail.mounted ? 'col-span-12 xl:col-span-8' : 'col-span-12'}>
          <InstrumentPanel
            title={
              selectedService
                ? `Single Service Route — ${selectedService.id}`
                : `Network Canvas — ${activeRegionObj.label} (${regionServices.length} Services)`
            }
            right={
              selectedService ? (
                <span className="text-cyan-400 font-bold text-[12px]">
                  ● SINGLE SERVICE INSPECTION · {selectedService.ports.join(' → ')}
                </span>
              ) : (
                <span className="flex items-center gap-2 flex-wrap justify-end">
                  <span className="text-slate-400 text-[12px]">{activeRegionObj.label} · {regionServices.length} SELECTED</span>
                  <button
                    type="button"
                    className="ni-layer-btn"
                    aria-pressed={showUnserved && !unservedNote}
                    disabled={Boolean(unservedNote)}
                    onClick={() => setShowUnserved((v) => !v)}
                    title={unservedNote || 'Ring each port by the TEU it could not ship or receive; dash the largest unserved lanes'}
                  >
                    <span className="ni-layer-key" aria-hidden="true" />
                    {unservedNote || `Unserved demand · ${fmtNum(activity.totals.unserved)} TEU`}
                  </button>
                </span>
              )
            }
            bodyPadding="flush"
          >
            <div ref={mapBoxRef} style={{ height: selectedService ? 440 : 460, scrollMarginTop: 56 }}>
              <WorldMap
                optimizationState={optState}
                selectedServices={regionServices}
                inspectedService={selectedService}
                regionFilter={activeRegion}
                onSelectService={inspectService}
                onClearService={handleClearService}
                focusPort={focusPort}
                unserved={showUnserved && !unservedNote ? activity : null}
                onPortOpen={openPortDrawer}
                openPort={openPort}
                drawKey={`${optState?.source?.url || ''}|${optState?.source?.modifiedIso || sm.run_id || ''}|network`}
              />
            </div>
          </InstrumentPanel>
        </div>

        {/* Right Column: Service Detail Side Panel (Only in Single Service Mode) */}
        {phone && (
          <BottomSheet open={Boolean(selectedService || openPort)}
            eyebrow={selectedService ? 'Service · from run' : `Port · ${demand ? 'run + dataset' : 'from run'}`}
            title={selectedService ? selectedService.id : openPort ? `${openPort} ${getPortName(openPort)}` : ''}
            onClose={selectedService ? handleClearService : () => setOpenPort(null)}>
            {selectedService ? <ServiceDetailPanel service={selectedService} /> : openPort ? (
              <PortDetailPanel code={openPort} activity={activity} tariffs={demand?.ports || null} hub={hubAt(transship.model, openPort)}
                onInspectService={inspectService} onOpenPort={openPortDrawer} />
            ) : null}
          </BottomSheet>
        )}
        {!phone && detail.mounted && shownService && (
          <div className="col-span-12 xl:col-span-4 ov-slide" data-state={detail.state}>
            <InstrumentPanel
              title={`Service Details — ${shownService.id}`}
              right={<span className="text-slate-400 font-bold text-[12px]">FROM RUN</span>}
              bodyPadding="flush"
            >
              <div style={{ maxHeight: 440, overflowY: 'auto' }}>
                <ServiceDetailPanel service={shownService} onClose={handleClearService} />
              </div>
            </InstrumentPanel>
          </div>
        )}
        {!phone && detail.mounted && shownPort && !shownService && (
          <div className="col-span-12 xl:col-span-4 ov-slide" data-state={detail.state}>
            <InstrumentPanel
              title={`Port — ${shownPort} ${getPortName(shownPort)}`}
              right={<span className="text-slate-400 font-bold text-[12px]">{demand ? 'RUN + DATASET' : 'FROM RUN'}</span>}
              bodyPadding="flush"
            >
              <div style={{ maxHeight: 460, overflowY: 'auto' }}>
                <PortDetailPanel
                  code={shownPort}
                  activity={activity}
                  hub={hubAt(transship.model, shownPort)}
                  tariffs={demand?.ports || null}
                  onInspectService={inspectService}
                  onOpenPort={openPortDrawer}
                  onClose={() => setOpenPort(null)}
                />
              </div>
            </InstrumentPanel>
          </div>
        )}
      </div>

      {/* ══ BOTTOM SECTION: SELECTED SERVICES TABLE + REGIONAL SPLIT ══ */}
      <div className="grid grid-cols-12 gap-3 items-stretch">
        {/* Left: Selected Services Table (8-cols) */}
        <div className="col-span-12 xl:col-span-8 flex flex-col h-full min-w-0">
          <InstrumentPanel
            title={`Selected Services (${regionServices.length} in ${activeRegionObj.label})`}
            right={
              <div className="flex items-center gap-2 flex-wrap justify-end">
                <button
                  type="button"
                  onClick={() => setLossOnly((v) => !v)}
                  aria-pressed={lossOnly}
                  disabled={lossCount === 0}
                  className={`px-2 py-0.5 text-[12px] rounded border font-mono ${lossOnly ? 'border-red-400 text-red-300 bg-red-500/10' : 'border-white/10 text-slate-300'} disabled:opacity-40`}
                  title="Show only services with negative weekly P&L"
                >
                  {lossCount} loss-making
                </button>
                <select
                  aria-label="Sort services"
                  value={sortKey}
                  onChange={(e) => setSortKey(e.target.value)}
                  className="px-1.5 py-0.5 text-[12px] rounded bg-black/60 border border-white/10 text-slate-200 font-mono"
                >
                  {Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select>
                <input
                  type="text"
                  aria-label="Filter services"
                  placeholder="Filter by ID, vessel, port..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="px-2 py-0.5 text-[12px] rounded bg-black/60 border border-white/10 text-slate-200 placeholder-slate-400 focus:outline-none focus:border-cyan-400 font-mono w-44"
                />
                <span className="text-[12px] text-slate-400">
                  {displayedServices.length} / {regionServices.length}
                </span>
                <button
                  type="button"
                  onClick={() => downloadCsv(`${optState?.source?.label || 'run'}_services`, [
                    ['service', (s) => s.id], ['region', (s) => s.region], ['agent', (s) => s.agent_region], ['vessel_class', (s) => s.vessel_class],
                    ['vessels', (s) => s.vessels], ['frequency_per_week', (s) => s.frequency_per_week], ['weekly_profit_usd', (s) => s.weekly_profit],
                    ['revenue_usd', (s) => s.revenue], ['cost_usd', (s) => s.cost], ['margin_pct', (s) => s.margin_pct], ['ports', (s) => (s.ports || []).join(' ')],
                  ], displayedServices)}
                  disabled={displayedServices.length === 0}
                  className="px-2 py-0.5 text-[12px] rounded border border-white/10 text-slate-300 font-mono disabled:opacity-40"
                  title="Save the rows shown as CSV"
                >
                  CSV
                </button>
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
                <div className="cx-rows flex-1" style={{ height: 410, maxHeight: 410, overflow: 'auto' }}>
                  {/* Table Header */}
                  <div
                    className="cx-row sticky top-0 bg-[#060c14] z-10 font-bold text-[12px] tracking-wider text-slate-400 border-b border-white/10"
                    style={{ display: 'grid', gridTemplateColumns: '150px 120px 100px minmax(160px, 1fr) 150px 80px', padding: '6px 10px', minWidth: 760 }}
                  >
                    <div>SERVICE ID</div>
                    <div title="Where most of the service's ports are. The optimizer agent that planned it is shown on hover over each region.">REGION</div>
                    <div>VESSEL</div>
                    <div>PORT SEQUENCE</div>
                    <div style={{ textAlign: 'right' }}>WEEKLY P&amp;L</div>
                    <div style={{ textAlign: 'right' }}>MARGIN</div>
                  </div>

                  {/* Table Rows */}
                  {displayedServices.map((s) => {
                    const isSelected = selectedService && selectedService.id === s.id;
                    const rColor = getRegionColor(s.region);
                    const isLoss = Number(s.weekly_profit) < 0;

                    return (
                      <div
                        key={s.id}
                        role="button"
                        tabIndex={0}
                        aria-label={`Inspect service ${s.id}`}
                        className={`cx-row transition-all text-[12px] hover:bg-white/[0.04] ${
                          isSelected ? 'bg-cyan-950/40' : ''
                        }`}
                        onClick={() => setSelectedService(s)}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedService(s); } }}
                        {...hoverProps('service', s.id)}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '150px 120px 100px minmax(160px, 1fr) 150px 80px',
                          padding: '6px 10px',
                          minWidth: 760,
                          cursor: 'pointer',
                          borderLeft: isSelected ? `3px solid ${rColor}` : (isLoss ? '3px solid rgba(255,95,99,0.55)' : '3px solid transparent'),
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
                            className="text-[12px] px-1.5 py-0.5 rounded font-semibold uppercase whitespace-nowrap"
                            style={{ background: `${rColor}20`, color: rColor }}
                            title={s.agent_region ? `Planned by the optimizer's "${s.agent_region}" agent` : undefined}
                          >
                            {s.region || '—'}
                          </span>
                        </div>

                        {/* Vessel */}
                        <div className="text-slate-300 truncate">{s.vessel_class || '—'}</div>

                        {/* Port Sequence */}
                        <div className="text-slate-300 truncate font-semibold">
                          {(s.ports || []).join(' → ')}
                          <span className="text-slate-400 font-normal text-[12px] ml-1">({fmtNum(s.load)} TEU)</span>
                        </div>

                        {/* Profit */}
                        <div className={`text-right font-bold ${pnlClass(s.weekly_profit)} cell-bar`}>
                          {s.weekly_profit != null && (
                            <span className="ibar" aria-hidden="true">
                              <span className={isLoss ? 'neg' : 'pos'} style={{ width: `${Math.max(4, (Math.abs(Number(s.weekly_profit)) / maxAbsPnl) * 100)}%` }} />
                            </span>
                          )}
                          {isLoss && <span className="sr-only">Loss: </span>}
                          {fmtUsd(s.weekly_profit)}
                        </div>

                        {/* Margin */}
                        <div className={`text-right font-semibold ${s.margin_pct != null && Number(s.margin_pct) < 0 ? 'text-red-400' : 'text-cyan-300'}`}>
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
        <div className="col-span-12 xl:col-span-4 flex flex-col justify-between h-full space-y-3">
          {/* Regional Split Breakdown */}
          <InstrumentPanel
            title="Regional Split Breakdown"
            right={<span className="text-[12px] text-slate-400 uppercase">{Object.keys(regionStats).length} REGIONS · BY PORT GEOGRAPHY</span>}
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
                      <span className="font-bold text-[12px] uppercase flex items-center gap-1.5" style={{ color: st.color }}>
                        <span className="w-2 h-2 rounded-full" style={{ background: st.color }} />
                        {st.name}
                      </span>
                      <span className="text-[12px] text-slate-300 font-bold">
                        {st.services} services{st.losses > 0 && <span className="text-red-400"> · {st.losses} loss</span>}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[12px]">
                      <div title="Sum of the selected services' own weekly P&L in this region">
                        <span className="text-slate-400">Σ service P&amp;L: </span>
                        <span className={`font-bold ${pnlClass(st.profit)}`}>{fmtUsd(st.profit)}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-slate-400">PORTS: </span>
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
              <div className="p-2 text-[12px] text-slate-400 leading-relaxed">
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
